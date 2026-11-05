"""Retained Livestock sweep registered through native CELERY_IMPORTS.

Executed by the native worker; no platform task/app or schedule is replaced.
"""

import logging

from celery import shared_task
from openg2p_registry_celery_worker.engine import Engine

from ..register_domain.services.approval_pending_reminder_service import (
    DEFAULT_STUCK_AFTER_DAYS, check_and_send_approval_pending_reminders,
)

_logger = logging.getLogger("g2p-livestock-schedules")


@shared_task(name="approval_pending_reminder_beat_producer")
def approval_pending_reminder_beat_producer():
    _logger.info("Running approval-pending reminder sweep (stuck > %d days)", DEFAULT_STUCK_AFTER_DAYS)
    sent = check_and_send_approval_pending_reminders(Engine.get_engine())
    _logger.info("Approval-pending reminder sweep: %d email(s) sent", sent)
    return sent
