"""Audit-log retention — G2R-135's "7-year retention period" requirement.

Deletes rows from g2p_register_audit_logs older than the retention window.
Touches ONLY that one table — never the actual register/history/intake-form
data, and never audit rows still inside the window. Kept as a plain,
directly-callable function (not celery-task-shaped) so it can be:
  - called from the scheduled celery-beat task (see
    ../../tasks/audit_log_retention_beat_producer.py) for the real,
    automatic 7-year cleanup, and
  - called directly (sync, no celery/broker needed) to test the exact same
    logic on demand — e.g. seed one old row + one recent row, run this, and
    check only the old one is gone.

Synchronous SQLAlchemy throughout (not the async engine the FastAPI apps use)
because celery-beat's own producers are sync — see
openg2p_registry_celery_beat.tasks.completion_score_beat_producer for the
precedent this follows.
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

_logger = logging.getLogger("g2p-audit-retention")

DEFAULT_RETENTION_YEARS = 7


def purge_expired_audit_logs(
    engine: Engine,
    retention_years: int = DEFAULT_RETENTION_YEARS,
    as_of: datetime | None = None,
) -> int:
    """Delete audit-log rows older than `retention_years` from `as_of`
    (defaults to now). Returns the number of rows deleted.

    `as_of` and `retention_years` are parameters (not hardcoded) purely so a
    test can pass a fixed clock and a short window instead of waiting years —
    production calls (the beat task) never override them.
    """
    # Resolve the model lazily, the same way domain_validation_utils and
    # audit_snapshot do: through the "openg2p_registry_extensions" alias
    # main.py points at this package's real module, not this package's own
    # dotted name — importing "..models" directly would load a second,
    # independent copy of every model and SQLAlchemy would refuse the
    # duplicate declarative Table registration.
    import importlib

    models = importlib.import_module("openg2p_registry_extensions.register_domain.models")
    G2PRegisterAuditLog = models.G2PRegisterAuditLog

    as_of = as_of or datetime.now()
    cutoff = as_of - timedelta(days=365 * retention_years)

    session_maker = sessionmaker(bind=engine, expire_on_commit=False)
    with session_maker() as session:
        result = session.execute(
            delete(G2PRegisterAuditLog).where(G2PRegisterAuditLog.event_timestamp < cutoff)
        )
        session.commit()
        deleted = result.rowcount or 0

    _logger.info(
        "Audit log retention: deleted %d row(s) older than %s (%d-year window)",
        deleted, cutoff.isoformat(), retention_years,
    )
    return deleted
