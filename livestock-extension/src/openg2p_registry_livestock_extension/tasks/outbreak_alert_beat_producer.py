"""Retained Livestock sweep registered through native CELERY_IMPORTS.

Executed by the native worker; no platform task/app or schedule is replaced.
"""

import logging

from celery import shared_task
from openg2p_registry_celery_worker.engine import Engine

from ..register_domain.services.outbreak_alert_service import (
    DEFAULT_THRESHOLD, DEFAULT_WINDOW_DAYS, check_and_alert_outbreaks,
)

_logger = logging.getLogger("g2p-livestock-schedules")


@shared_task(name="outbreak_alert_beat_producer")
def outbreak_alert_beat_producer():
    _logger.info(
        "Running outbreak alert sweep (%d+ notifiable cases, %d-day window)",
        DEFAULT_THRESHOLD, DEFAULT_WINDOW_DAYS,
    )
    alerted = check_and_alert_outbreaks(Engine.get_engine())
    _logger.info("Outbreak alert sweep: %d new alert(s) sent", len(alerted))
    return len(alerted)
