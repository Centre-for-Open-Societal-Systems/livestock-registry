"""Re-drive deliveries that failed only because no registry signing key was available.

The published connector keeps the raw delivered body in ``dead_letter_queue.payload`` for every
failed run. A delivery that failed with "Registry signature is not configured" is therefore
fully recoverable once a key exists, without the hub redelivering and without an admin token.

A Celery beat task (``connector.oan_redrive_unsigned``, every ``INTERVAL_SECONDS``) replays those
entries through the normal ``IngestionService.process_record`` pipeline:

* only entries whose error starts with the signature marker, and only when a key can now be
  resolved for the entry's connector (otherwise the entry is left alone, nothing is logged per tick);
* at most ``BATCH`` entries per tick and ``MAX_ATTEMPTS`` tries per entry;
* success deletes the entry (as ``POST /dlq/replay`` does) and records the idempotency key, so a
  later hub redelivery of the same event is a no-op; the original FAILED run stays as history;
* any other outcome is rolled back (no extra run or DLQ row), the entry's error is replaced by
  the new one and its attempt count rises, so it leaves the selection and shows its real cause
  for an operator's ``POST /dlq/replay``.
"""

import logging
from typing import Any

from . import registry_signature

_logger = logging.getLogger("connector.extension.requeue")

MARKER = "Registry signature is not configured"
INTERVAL_SECONDS = 300
BATCH = 50
MAX_ATTEMPTS = 5
TASK_NAME = "connector.oan_redrive_unsigned"


async def redrive(session_factory, service, *, entry_model=None, connector_model=None, select=None) -> dict[str, Any]:
    """Replay up to BATCH marked entries. The model classes and ``select`` default to the connector's own."""
    if entry_model is None:
        from openg2p_connector_service.models import ConnectorDefinition, DeadLetterEntry
        from sqlalchemy import select as sa_select

        entry_model, connector_model, select = DeadLetterEntry, ConnectorDefinition, sa_select
    stats = {"candidates": 0, "replayed": 0, "failed": 0, "skipped": 0}

    async with session_factory() as session:
        rows = await session.execute(
            select(entry_model.dl_id)
            .where(entry_model.error.like(MARKER + "%"), entry_model.attempt_count < MAX_ATTEMPTS)
            .order_by(entry_model.created_at)
            .limit(BATCH)
        )
        dl_ids = list(rows.scalars().all())
    stats["candidates"] = len(dl_ids)

    for dl_id in dl_ids:
        try:
            outcome = await _redrive_one(session_factory, service, dl_id, entry_model, connector_model)
        except Exception:
            _logger.warning("Re-drive of dead-letter entry %s raised", dl_id, exc_info=True)
            outcome = "failed"
        stats[outcome] += 1
    if stats["replayed"] or stats["failed"]:
        _logger.info("Re-drove unsigned deliveries: %s", stats)
    return stats


async def _redrive_one(session_factory, service, dl_id, entry_model, connector_model) -> str:
    async with session_factory() as session:
        entry = await session.get(entry_model, dl_id)
        if entry is None:
            return "skipped"
        connector = await session.get(connector_model, entry.connector_id)
        if connector is None or not connector.is_active:
            return "skipped"
        try:
            registry_signature.signing_key(connector)
        except ValueError:
            return "skipped"  # still no key: leave it for a later tick
        run = await service.process_record(
            connector=connector,
            source_event_id=entry.source_event_id,
            raw_data=entry.payload or {},
            session=session,
        )
        if run.status.value == "SUCCESS":
            await session.delete(entry)
            await session.commit()
            return "replayed"
        error = (run.last_error or "re-drive failed")[:2000]
        await session.rollback()

    async with session_factory() as session:
        entry = await session.get(entry_model, dl_id)
        if entry is not None:
            entry.attempt_count = (entry.attempt_count or 0) + 1
            entry.error = error
            await session.commit()
    return "failed"
