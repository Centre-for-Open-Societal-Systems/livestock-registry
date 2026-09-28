"""Scheduled celery-beat task: vaccination due-soon / overdue email reminders,
plus the Vaccination Status UP_TO_DATE -> OVERDUE auto-flip
(vaccination_status_service.py) — piggybacked onto the same daily task rather
than a separate core-patch/schedule entry, since both are "check every
vaccination against today's date" sweeps that belong together.

Registered onto celery-beat's OWN celery_app via a build-time core-patch —
see docker/celery/core-patches/apply_patches.py — the same pattern
audit_log_retention_beat_producer.py / outbreak_alert_beat_producer.py follow.
"""

import logging

from openg2p_registry_celery_beat.app import celery_app
from openg2p_registry_celery_beat.config import Settings
from openg2p_registry_celery_beat.engine import Engine

from ..register_domain.services.vaccination_reminder_service import (
    check_and_send_vaccination_reminders,
)
from ..register_domain.services.vaccination_status_service import flag_overdue_vaccinations

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)
_engine = Engine.get_engine()


@celery_app.task(name="vaccination_reminder_beat_producer")
def vaccination_reminder_beat_producer():
    _logger.info("Running vaccination due-soon/overdue reminder sweep")
    counts = check_and_send_vaccination_reminders(_engine)
    _logger.info(
        "Vaccination reminder sweep: %d due-soon, %d overdue email(s) sent",
        counts["due_soon"], counts["overdue"],
    )

    flagged = flag_overdue_vaccinations(_engine)
    _logger.info("Vaccination status sweep: %d animal(s) flagged OVERDUE", len(flagged))
    counts["flagged_overdue"] = len(flagged)
    return counts
