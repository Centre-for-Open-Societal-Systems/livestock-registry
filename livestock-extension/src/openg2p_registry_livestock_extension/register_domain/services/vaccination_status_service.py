"""Vaccination Status auto-flip: UP_TO_DATE -> OVERDUE once the animal's most
recent vaccination's next_due_date has passed.

Mirrors gen1's `g2p.livestock.vaccination._cron_flag_overdue_vaccinations()`
(g2p_livestock_registry/models/livestock_event.py). UP_TO_DATE is set the
moment a Vaccination is logged (see
g2p_register_domain_service_vaccination.py's post_approve/post_ingest); this
sweep is the other half — the daily check that notices time has passed the
due date and flips the animal's status forward. Unlike the email reminders
(vaccination_reminder_service.py), this changes the animal's own record, not
just a notification, so it needs no dedup/tracking table of its own — a
NOT-yet-OVERDUE animal past its due date is, by definition, something this
sweep should always correct, every run, until a fresh vaccination is logged
(post_approve/post_ingest resets it to UP_TO_DATE again).

Plain, engine-parameterized function for the same reason the other reminder
services are — callable from the scheduled celery-beat task
(vaccination_reminder_beat_producer.py, which already runs the vaccination
email reminders daily — this sweep piggybacks on that same task rather than
adding a whole new core-patch/schedule entry) and callable directly for a
same-day test.
"""

import logging
from datetime import date

from sqlalchemy import text
from sqlalchemy.engine import Engine

_logger = logging.getLogger("g2p-reminder-alerts")


def flag_overdue_vaccinations(engine: Engine, as_of: date | None = None) -> list[str]:
    """Flip every animal whose most recent vaccination's next_due_date has
    passed from UP_TO_DATE to OVERDUE. "Most recent" = highest
    vaccination_date on file for that (ear_tag_id, livestock) pair — an
    earlier vaccination's due date doesn't matter once a later one has been
    logged. Returns the ear tags flipped this run.
    """
    as_of = as_of or date.today()

    query = text("""
        WITH latest_vaccination AS (
            SELECT DISTINCT ON (ear_tag_id, link_internal_record_id)
                ear_tag_id, link_internal_record_id, next_due_date
            FROM g2p_register_vaccinations
            WHERE record_status = 'ACTIVE' AND ear_tag_id IS NOT NULL
            ORDER BY ear_tag_id, link_internal_record_id, vaccination_date DESC NULLS LAST
        )
        UPDATE g2p_register_animals a
        SET vaccination_status = 'OVERDUE'
        FROM latest_vaccination lv
        WHERE a.ear_tag_id = lv.ear_tag_id
          AND a.link_internal_record_id = lv.link_internal_record_id
          AND a.record_status = 'ACTIVE'
          AND a.vaccination_status = 'UP_TO_DATE'
          AND lv.next_due_date IS NOT NULL
          AND lv.next_due_date < :as_of
        RETURNING a.ear_tag_id
    """)

    with engine.begin() as conn:
        flagged = conn.execute(query, {"as_of": as_of}).scalars().all()

    if flagged:
        _logger.info("Vaccination status: flagged %d animal(s) OVERDUE: %s", len(flagged), flagged)
    return list(flagged)
