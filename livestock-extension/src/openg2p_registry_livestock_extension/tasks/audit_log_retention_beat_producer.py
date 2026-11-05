"""Retained Livestock sweep registered through native CELERY_IMPORTS.

Executed by the native worker; no platform task/app or schedule is replaced.
"""

import logging

from celery import shared_task
from openg2p_registry_celery_worker.engine import Engine

from ..register_domain.services.audit_retention_service import (
    DEFAULT_RETENTION_YEARS,
    purge_expired_audit_logs,
)

_logger = logging.getLogger("g2p-livestock-schedules")


@shared_task(name="audit_log_retention_beat_producer")
def audit_log_retention_beat_producer():
    _logger.info("Running audit log retention (%d-year window)", DEFAULT_RETENTION_YEARS)
    deleted = purge_expired_audit_logs(Engine.get_engine())
    _logger.info("Audit log retention: removed %d row(s) past retention", deleted)
    return deleted
