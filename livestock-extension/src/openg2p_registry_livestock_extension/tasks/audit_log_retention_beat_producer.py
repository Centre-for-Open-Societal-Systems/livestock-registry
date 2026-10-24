"""Scheduled celery-beat task for G2R-135's audit-log retention requirement.

Registered onto celery-beat's OWN celery_app (not a new one) via a build-time
core-patch — see docker/celery/core-patches/apply_patches.py — which is the
same "thin extension adds only the livestock domain model" pattern the rest
of this image already follows (docker/celery/Dockerfile), just extended to
cover a scheduled task rather than a domain model/service.
"""

import logging

from openg2p_registry_celery_beat.app import celery_app
from openg2p_registry_celery_beat.config import Settings
from openg2p_registry_celery_beat.engine import Engine

from ..register_domain.services.audit_retention_service import (
    DEFAULT_RETENTION_YEARS,
    purge_expired_audit_logs,
)

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)
_engine = Engine.get_engine()


@celery_app.task(name="audit_log_retention_beat_producer")
def audit_log_retention_beat_producer():
    _logger.info("Running audit log retention (%d-year window)", DEFAULT_RETENTION_YEARS)
    deleted = purge_expired_audit_logs(_engine)
    _logger.info("Audit log retention: removed %d row(s) past retention", deleted)
    return deleted
