"""Scheduled celery-beat task: 3+ notifiable-disease cases of the same
disease in the same district within 14 days -> automatic alert email to
district/regional vet officers.

Registered onto celery-beat's OWN celery_app (not a new one) via a build-time
core-patch — see docker/celery/core-patches/apply_patches.py — the same
pattern audit_log_retention_beat_producer.py already follows.
"""

import logging

from openg2p_registry_celery_beat.app import celery_app
from openg2p_registry_celery_beat.config import Settings
from openg2p_registry_celery_beat.engine import Engine

from ..register_domain.services.outbreak_alert_service import (
    DEFAULT_THRESHOLD, DEFAULT_WINDOW_DAYS, check_and_alert_outbreaks,
)

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)
_engine = Engine.get_engine()


@celery_app.task(name="outbreak_alert_beat_producer")
def outbreak_alert_beat_producer():
    _logger.info(
        "Running outbreak alert sweep (%d+ notifiable cases, %d-day window)",
        DEFAULT_THRESHOLD, DEFAULT_WINDOW_DAYS,
    )
    alerted = check_and_alert_outbreaks(_engine)
    _logger.info("Outbreak alert sweep: %d new alert(s) sent", len(alerted))
    return len(alerted)
