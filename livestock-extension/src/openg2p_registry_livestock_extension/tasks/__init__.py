"""Domain-owned native Celery imports and additive schedules."""
from celery import current_app
from .audit_log_retention_beat_producer import audit_log_retention_beat_producer
from .outbreak_alert_beat_producer import outbreak_alert_beat_producer
from .vaccination_reminder_beat_producer import vaccination_reminder_beat_producer
from .approval_pending_reminder_beat_producer import approval_pending_reminder_beat_producer
from .calving_reminder_beat_producer import calving_reminder_beat_producer

DOMAIN_SCHEDULE = {
    "audit_log_retention_beat_producer": 86400.0,
    "outbreak_alert_beat_producer": 900.0,
    "vaccination_reminder_beat_producer": 86400.0,
    "approval_pending_reminder_beat_producer": 86400.0,
    "calving_reminder_beat_producer": 86400.0,
}
current_app.conf.beat_schedule = {
    **(current_app.conf.beat_schedule or {}),
    **{name: {"task": name, "schedule": frequency} for name, frequency in DOMAIN_SCHEDULE.items()},
}
