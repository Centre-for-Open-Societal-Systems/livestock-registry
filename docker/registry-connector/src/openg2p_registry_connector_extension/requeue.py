"""Re-drive deliveries that failed only because no registry signing key was available.

The published connector keeps the raw delivered body in ``dead_letter_queue.payload`` for every
failed run. A delivery that failed with "Registry signature is not configured" is therefore
fully recoverable once a key exists, without the hub redelivering and without an admin token.

A Celery beat task (``connector.oan_redrive_unsigned``, every ``INTERVAL_SECONDS``) replays those
entries through the normal ``IngestionService.process_record`` pipeline:

* only entries whose error starts with the signature marker, and only for connectors that are
  active and can now resolve a key (the others are filtered out before the batch window, so they
  never block it, and are left alone without logging per tick);
* at most ``BATCH`` entries per tick and ``MAX_ATTEMPTS`` tries per entry; each entry is locked
  (``FOR UPDATE SKIP LOCKED``) while it is replayed, so overlapping ticks never replay it twice;
* success deletes the entry (as ``POST /dlq/replay`` does) and records the idempotency key, so a
  later hub redelivery of the same event is a no-op; the original FAILED run stays as history;
* any other outcome, including an exception, is rolled back (no extra run or DLQ row), the entry's error is replaced by
  the new one and its attempt count rises, so it leaves the selection and shows its real cause
  for an operator's ``POST /dlq/replay``.
"""

import logging
from typing import Any

from . import registry_signature

_logger = logging.getLogger("connector.extension.requeue")

MARKER = "Registry signature is not configured"
INTERVAL_SECONDS = 300
TIME_LIMIT_SECONDS = 240  # below the period, so a stuck tick is killed before the next one starts
BATCH = 50
MAX_ATTEMPTS = 5
TASK_NAME = "connector.oan_redrive_unsigned"


async def redrive(session_factory, service, *, entry_model=None, connector_model=None, select=None) -> dict[str, Any]:
    """Replay up to BATCH marked entries. The model classes and ``select`` default to the connector's own."""
    db_errors: tuple = ()
    if entry_model is None:
        from openg2p_connector_service.models import ConnectorDefinition, DeadLetterEntry
        from sqlalchemy import select as sa_select
        from sqlalchemy.exc import OperationalError, ProgrammingError

        entry_model, connector_model, select = DeadLetterEntry, ConnectorDefinition, sa_select
        db_errors = (OperationalError, ProgrammingError)
    stats = {"candidates": 0, "replayed": 0, "failed": 0, "skipped": 0}

    try:
        dl_ids = await _candidates(session_factory, entry_model, connector_model, select)
    except db_errors as exc:  # e.g. the dead-letter table does not exist yet
        _logger.warning("Re-drive skipped, dead-letter table not readable: %s", type(exc).__name__)
        return stats
    stats["candidates"] = len(dl_ids)

    for dl_id in dl_ids:
        try:
            outcome = await _redrive_one(session_factory, service, dl_id, entry_model, connector_model, select)
        except Exception as exc:
            _logger.warning("Re-drive of dead-letter entry %s raised", dl_id, exc_info=True)
            outcome = "failed"
            try:
                reason = f"Re-drive raised {type(exc).__name__}: {exc}"
                await _record_failure(session_factory, entry_model, dl_id, reason)
            except Exception:
                _logger.warning("Could not record the re-drive failure of %s", dl_id, exc_info=True)
        stats[outcome] += 1
    if stats["replayed"] or stats["failed"]:
        _logger.info("Re-drove unsigned deliveries: %s", stats)
    return stats


async def _candidates(session_factory, entry_model, connector_model, select) -> list[str]:
    """Marked entries of connectors that are active and can sign now, oldest first, at most BATCH."""
    marked = (entry_model.error.like(MARKER + "%"), entry_model.attempt_count < MAX_ATTEMPTS)
    async with session_factory() as session:
        connector_ids = list((await session.execute(
            select(entry_model.connector_id).where(*marked).distinct())).scalars().all())
        able = []
        for connector_id in connector_ids:
            connector = await session.get(connector_model, connector_id)
            if connector is None or not connector.is_active:
                continue
            try:
                registry_signature.signing_key(connector)
            except ValueError:
                continue  # still no key: leave its entries for a later tick
            able.append(connector_id)
        if not able:
            return []
        rows = await session.execute(
            select(entry_model.dl_id)
            .where(*marked, entry_model.connector_id.in_(able))
            .order_by(entry_model.created_at)
            .limit(BATCH)
        )
        return list(rows.scalars().all())


async def _redrive_one(session_factory, service, dl_id, entry_model, connector_model, select) -> str:
    async with session_factory() as session:
        entry = (await session.execute(
            select(entry_model).where(entry_model.dl_id == dl_id).with_for_update(skip_locked=True)
        )).scalar_one_or_none()
        if entry is None:
            return "skipped"  # gone, or another tick holds it
        connector = await session.get(connector_model, entry.connector_id)
        if connector is None or not connector.is_active:
            return "skipped"
        try:
            registry_signature.signing_key(connector)
        except ValueError:
            return "skipped"
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
    await _record_failure(session_factory, entry_model, dl_id, error)
    return "failed"


async def _record_failure(session_factory, entry_model, dl_id, error: str) -> None:
    """Count the try and replace the marker, so the entry leaves the selection and shows its real cause."""
    async with session_factory() as session:
        entry = await session.get(entry_model, dl_id)
        if entry is not None:
            entry.attempt_count = (entry.attempt_count or 0) + 1
            entry.error = error[:2000]
            await session.commit()
