"""Vaccination due-soon / overdue email reminders.

Mirrors gen1's `g2p.livestock.vaccination._cron_send_vaccination_reminders()`
(g2p_livestock_registry/models/livestock_event.py) — one email when a
vaccination's `next_due_date` is within the next few days, and another once
it's actually overdue. Gen1 emailed the specific user who logged the
vaccination (`administering_user_id`); gen2's `administered_by` is a plain
free-text string (no user/email directory behind it), so recipients come
from env config instead — see `reminder_alert_utils.resolve_recipients`.

Plain, directly-callable functions (not celery-task-shaped) for the same
reason outbreak_alert_service is: callable from the scheduled celery-beat
task (../../tasks/vaccination_reminder_beat_producer.py) for the real,
periodic sweep, and callable directly to test the same logic on demand.
"""

import logging

from sqlalchemy import text
from sqlalchemy.engine import Engine

from .reminder_alert_utils import (
    already_sent, animal_not_deceased_sql, ensure_tracking_table, record_sent, resolve_recipients,
    send_email, today,
)

_logger = logging.getLogger("g2p-reminder-alerts")

DEFAULT_DUE_SOON_WINDOW_DAYS = 3

_DUE_SOON_TYPE = "vaccination_due_soon"
_OVERDUE_TYPE = "vaccination_overdue"


def _fetch(engine: Engine, query: str, params: dict) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(text(query), params).mappings().all()
    return [dict(row) for row in rows]


def find_due_soon(engine: Engine, window_days: int = DEFAULT_DUE_SOON_WINDOW_DAYS, as_of=None) -> list[dict]:
    as_of = as_of or today()
    from datetime import timedelta
    cutoff = as_of + timedelta(days=window_days)
    return _fetch(engine, f"""
        SELECT v.internal_record_id, v.ear_tag_id, v.vaccine_type, v.next_due_date
        FROM g2p_register_vaccinations v
        WHERE v.record_status = 'ACTIVE'
          AND v.next_due_date IS NOT NULL
          AND v.next_due_date >= :today AND v.next_due_date <= :cutoff
          AND {animal_not_deceased_sql("v")}
        ORDER BY v.next_due_date
    """, {"today": as_of, "cutoff": cutoff})


def find_overdue(engine: Engine, as_of=None) -> list[dict]:
    as_of = as_of or today()
    return _fetch(engine, f"""
        SELECT v.internal_record_id, v.ear_tag_id, v.vaccine_type, v.next_due_date
        FROM g2p_register_vaccinations v
        WHERE v.record_status = 'ACTIVE'
          AND v.next_due_date IS NOT NULL
          AND v.next_due_date < :today
          AND {animal_not_deceased_sql("v")}
        ORDER BY v.next_due_date
    """, {"today": as_of})


def _send_reminder(engine: Engine, reminder_type: str, subject_prefix: str, rec: dict) -> bool:
    if already_sent(engine, reminder_type, rec["internal_record_id"], rec["next_due_date"]):
        return False

    recipients = resolve_recipients("VACCINATION_REMINDER_FALLBACK_EMAILS")
    subject = f"{subject_prefix}: {rec['vaccine_type'] or 'vaccination'} for {rec['ear_tag_id'] or 'animal'}"
    body = (
        f"Ear tag: {rec.get('ear_tag_id') or '-'}\n"
        f"Vaccine: {rec.get('vaccine_type') or '-'}\n"
        f"Next due date: {rec['next_due_date']}\n\n"
        "This is an automated reminder from the Livestock Registry."
    )
    sent = send_email(subject, body, recipients)
    if sent:
        record_sent(engine, reminder_type, rec["internal_record_id"], rec["next_due_date"], recipients)
    return sent


def check_and_send_vaccination_reminders(
    engine: Engine, window_days: int = DEFAULT_DUE_SOON_WINDOW_DAYS, as_of=None,
) -> dict:
    """Run one sweep: email every not-yet-reminded due-soon and overdue
    vaccination. Returns {"due_soon": n, "overdue": n} counts of emails
    actually sent this run.
    """
    ensure_tracking_table(engine)

    due_soon_sent = sum(
        1 for rec in find_due_soon(engine, window_days, as_of)
        if _send_reminder(engine, _DUE_SOON_TYPE, "Reminder: Vaccination due soon", rec)
    )
    overdue_sent = sum(
        1 for rec in find_overdue(engine, as_of)
        if _send_reminder(engine, _OVERDUE_TYPE, "Overdue: Vaccination is past due", rec)
    )

    _logger.info("Vaccination reminders: %d due-soon, %d overdue", due_soon_sent, overdue_sent)
    return {"due_soon": due_soon_sent, "overdue": overdue_sent}
