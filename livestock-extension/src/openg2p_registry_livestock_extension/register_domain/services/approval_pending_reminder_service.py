"""Approval-pending-too-long email reminder.

Mirrors gen1's `g2p.livestock.registry._cron_send_approval_pending_reminders()`
(g2p_livestock_registry/models/livestock_registry.py) — emails the next
approver when a Livestock record has been sitting at the same
Kebele/Woreda/Zone/Region approval stage for too long (default 3 days)
without moving forward. Gen1 matched `res.users` group membership scoped to
the record's kebele/woreda/zone/region; gen2 has no equivalent
approver-directory, so recipients come from env config's district mapping
instead (the record's own kebele/woreda/zone/region — whichever matches the
stage that's stuck — is passed as the "district" key; see
reminder_alert_utils.resolve_recipients).

Plain, directly-callable functions for the same reason the other reminder
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

DEFAULT_STUCK_AFTER_DAYS = 3
_REMINDER_TYPE = "approval_pending"

# state -> which G2PAdminArea column names the next approver for that stage,
# mirroring gen1's _APPROVAL_REMINDER_MAP (kebele approver clears DRAFT,
# woreda approver clears KEBELE_APPROVED, etc.) — VERIFIED/ARCHIVED are
# terminal, never "stuck".
_STAGE_LOCATION_COLUMN = {
    "DRAFT": "kebele",
    "KEBELE_APPROVED": "woreda",
    "WOREDA_APPROVED": "zone",
    "ZONE_APPROVED": "region",
}


def find_stuck_records(engine: Engine, stuck_after_days: int = DEFAULT_STUCK_AFTER_DAYS, as_of=None) -> list[dict]:
    as_of = as_of or today()
    cutoff = as_of - timedelta(days=stuck_after_days)

    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT internal_record_id, functional_record_id, farmer_name, state, state_date,
                       kebele, woreda, zone, region
                FROM g2p_register_livestocks
                WHERE record_status = 'ACTIVE'
                  AND state IN ('DRAFT', 'KEBELE_APPROVED', 'WOREDA_APPROVED', 'ZONE_APPROVED')
                  AND state_date IS NOT NULL AND state_date <= :cutoff
                ORDER BY state_date
            """),
            {"cutoff": cutoff},
        ).mappings().all()

    return [dict(row) for row in rows]


def check_and_send_approval_pending_reminders(
    engine: Engine, stuck_after_days: int = DEFAULT_STUCK_AFTER_DAYS, as_of=None,
) -> int:
    """Run one sweep: email every not-yet-reminded record stuck at its
    current approval stage. Returns the number of emails actually sent.
    `reminder_key` is the record's `state`, so a record that moves forward
    (or moves back) gets a fresh reminder if it later gets stuck again at a
    *different* stage, without re-emailing for the same stuck stage twice.
    """
    ensure_tracking_table(engine)

    sent_count = 0
    for rec in find_stuck_records(engine, stuck_after_days, as_of):
        if already_sent(engine, _REMINDER_TYPE, rec["internal_record_id"], rec["state"]):
            continue

        location_column = _STAGE_LOCATION_COLUMN.get(rec["state"])
        district = rec.get(location_column) if location_column else None
        recipients = resolve_recipients(
            "APPROVAL_REMINDER_FALLBACK_EMAILS", "APPROVAL_REMINDER_DISTRICT_EMAILS", district,
        )

        subject = f"Action needed: {rec.get('functional_record_id') or 'a Livestock record'} awaiting your approval"
        body = (
            f"Farmer: {rec.get('farmer_name') or '-'}\n"
            f"Record: {rec.get('functional_record_id') or rec['internal_record_id']}\n"
            f"Stuck at stage: {rec['state']}\n"
            f"Since: {rec['state_date']}\n\n"
            "This record has been waiting at this approval stage for several days and needs review.\n\n"
            "This is an automated reminder from the Livestock Registry."
        )
        sent = send_email(subject, body, recipients)
        if sent:
            record_sent(engine, _REMINDER_TYPE, rec["internal_record_id"], rec["state"], recipients)
            sent_count += 1

    _logger.info("Approval-pending reminders: %d sent", sent_count)
    return sent_count
