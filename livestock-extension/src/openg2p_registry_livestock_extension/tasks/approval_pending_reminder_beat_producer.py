"""Scheduled celery-beat task: approval-pending-too-long email reminder.

Registered onto celery-beat's OWN celery_app via a build-time core-patch —
see docker/celery/core-patches/apply_patches.py.
"""

import logging

from openg2p_registry_celery_beat.app import celery_app
from openg2p_registry_celery_beat.config import Settings
from openg2p_registry_celery_beat.engine import Engine

from ..register_domain.services.approval_pending_reminder_service import (
    DEFAULT_STUCK_AFTER_DAYS, check_and_send_approval_pending_reminders,
)

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)
_engine = Engine.get_engine()


@celery_app.task(name="approval_pending_reminder_beat_producer")
def approval_pending_reminder_beat_producer():
    _logger.info("Running approval-pending reminder sweep (stuck > %d days)", DEFAULT_STUCK_AFTER_DAYS)
    sent = check_and_send_approval_pending_reminders(_engine)
    _logger.info("Approval-pending reminder sweep: %d email(s) sent", sent)
    return sent
