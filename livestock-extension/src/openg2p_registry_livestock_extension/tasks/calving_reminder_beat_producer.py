"""Retained Livestock sweep registered through native CELERY_IMPORTS.

Executed by the native worker; no platform task/app or schedule is replaced.
"""

import logging

from celery import shared_task
from openg2p_registry_celery_worker.engine import Engine

from ..register_domain.services.calving_reminder_service import (
    DEFAULT_WINDOW_DAYS, check_and_send_calving_reminders,
)

_logger = logging.getLogger("g2p-livestock-schedules")


@shared_task(name="calving_reminder_beat_producer")
def calving_reminder_beat_producer():
    _logger.info("Running upcoming-birth reminder sweep (%d-day window)", DEFAULT_WINDOW_DAYS)
    sent = check_and_send_calving_reminders(Engine.get_engine())
    _logger.info("Upcoming-birth reminder sweep: %d email(s) sent", sent)
    return sent
