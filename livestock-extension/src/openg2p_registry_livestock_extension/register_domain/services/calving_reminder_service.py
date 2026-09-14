"""Upcoming-birth (calving) email reminder.

Mirrors gen1's `g2p.livestock.breeding._cron_send_calving_reminders()`
(g2p_livestock_registry/models/livestock_event.py) — emails when a Breeding
record's `expected_calving_date` is coming up within the next 7 days, while
the pregnancy outcome is still PENDING (not yet confirmed as a birth or
marked failed), so the field officer can be ready to record the outcome.
Gen1 emailed whoever logged the breeding record (`create_uid`); gen2's
`created_by` on the register base is a plain display-name string (no
directory behind it to resolve an email from), so recipients come from env
config instead — see reminder_alert_utils.resolve_recipients.

Plain, directly-callable function for the same reason the other reminder
services are.
"""

import logging
from datetime import timedelta

from sqlalchemy import text
from sqlalchemy.engine import Engine

from .reminder_alert_utils import (
    already_sent, ensure_tracking_table, record_sent, resolve_recipients, send_email, today,
)

_logger = logging.getLogger("g2p-reminder-alerts")

DEFAULT_WINDOW_DAYS = 7
_REMINDER_TYPE = "calving_due_soon"


def find_upcoming_calvings(engine: Engine, window_days: int = DEFAULT_WINDOW_DAYS, as_of=None) -> list[dict]:
    as_of = as_of or today()
    cutoff = as_of + timedelta(days=window_days)

    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT internal_record_id, ear_tag_id, expected_calving_date
                FROM g2p_register_breedings
                WHERE record_status = 'ACTIVE'
                  AND outcome = 'PENDING'
                  AND expected_calving_date IS NOT NULL
                  AND expected_calving_date >= :today AND expected_calving_date <= :cutoff
                ORDER BY expected_calving_date
            """),
            {"today": as_of, "cutoff": cutoff},
        ).mappings().all()

    return [dict(row) for row in rows]


def check_and_send_calving_reminders(engine: Engine, window_days: int = DEFAULT_WINDOW_DAYS, as_of=None) -> int:
    """Run one sweep: email every not-yet-reminded upcoming calving.
    Returns the number of emails actually sent this run.
    """
    ensure_tracking_table(engine)

    sent_count = 0
    for rec in find_upcoming_calvings(engine, window_days, as_of):
        if already_sent(engine, _REMINDER_TYPE, rec["internal_record_id"], rec["expected_calving_date"]):
            continue

        recipients = resolve_recipients("CALVING_REMINDER_FALLBACK_EMAILS")
        subject = f"Upcoming birth: {rec.get('ear_tag_id') or 'animal'} expected around {rec['expected_calving_date']}"
        body = (
            f"Ear tag: {rec.get('ear_tag_id') or '-'}\n"
            f"Expected calving date: {rec['expected_calving_date']}\n\n"
            "Please be ready to record the birth outcome (Vital Event) around this date.\n\n"
            "This is an automated reminder from the Livestock Registry."
        )
        sent = send_email(subject, body, recipients)
        if sent:
            record_sent(engine, _REMINDER_TYPE, rec["internal_record_id"], rec["expected_calving_date"], recipients)
            sent_count += 1

    _logger.info("Calving reminders: %d sent", sent_count)
    return sent_count
