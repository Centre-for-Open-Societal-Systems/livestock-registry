"""Retained Livestock sweep registered through native CELERY_IMPORTS.

Executed by the native worker; no platform task/app or schedule is replaced.
"""

import logging

from celery import shared_task
from openg2p_registry_celery_worker.engine import Engine

from ..register_domain.services.vaccination_reminder_service import (
    check_and_send_vaccination_reminders,
)
from ..register_domain.services.vaccination_status_service import flag_overdue_vaccinations

_logger = logging.getLogger("g2p-livestock-schedules")


@shared_task(name="vaccination_reminder_beat_producer")
def vaccination_reminder_beat_producer():
    _logger.info("Running vaccination due-soon/overdue reminder sweep")
    counts = check_and_send_vaccination_reminders(Engine.get_engine())
    _logger.info(
        "Vaccination reminder sweep: %d due-soon, %d overdue email(s) sent",
        counts["due_soon"], counts["overdue"],
    )

    flagged = flag_overdue_vaccinations(Engine.get_engine())
    _logger.info("Vaccination status sweep: %d animal(s) flagged OVERDUE", len(flagged))
    counts["flagged_overdue"] = len(flagged)
    return counts
