"""Shared plumbing for the registry's periodic email reminders:
  - vaccination due soon / overdue      (vaccination_reminder_service.py)
  - approval pending too long           (approval_pending_reminder_service.py)
  - upcoming birth / calving            (calving_reminder_service.py)
  - notifiable-disease outbreak alert   (outbreak_alert_service.py — has its
    own copy of the SMTP-send step, predating this module; left untouched
    since it's already tested/deployed, but conceptually the same relay)

Mirrors gen1's per-feature `mail.template` + cron pattern
(g2p_livestock_registry/models/livestock_event.py /livestock_registry.py),
minus the mail.thread infrastructure gen2's headless stack doesn't have, and
minus a real per-district/per-user contact directory (see
`resolve_recipients` docstring) — recipients come from env config instead.

Dedup: a single generic tracking table (`g2p_reminder_emails_sent`) rather
than a `*_reminder_sent` boolean column per feature — adding a column to an
existing register table needs a migration for every environment; a fresh,
purpose-built table only needs `CREATE TABLE IF NOT EXISTS`, created here
directly the same way outbreak_alert_service.py creates its own tracking
table (new tables do not reliably auto-create on this stack — see
[[livestock-species-conditional-identifier]] project memory). One row per
(reminder_type, record, reminder_key); `reminder_key` is normally the date or
state the reminder is ABOUT (e.g. the due date, or the approval stage) so
that if that value changes — vaccination re-scheduled, record approved to
the next stage — a fresh reminder can fire again for the new value, the same
effect gen1 got by resetting its boolean flag in `write()`.
"""

import logging
import os
import smtplib
from datetime import date
from email.mime.text import MIMEText

from sqlalchemy import text
from sqlalchemy.engine import Engine

_logger = logging.getLogger("g2p-reminder-alerts")

_TRACKING_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS g2p_reminder_emails_sent (
    id SERIAL PRIMARY KEY,
    reminder_type VARCHAR NOT NULL,
    record_internal_id VARCHAR NOT NULL,
    reminder_key VARCHAR NOT NULL,
    sent_at TIMESTAMP NOT NULL DEFAULT now(),
    recipients TEXT,
    UNIQUE (reminder_type, record_internal_id, reminder_key)
)
"""


def animal_not_deceased_sql(event_alias: str) -> str:
    """SQL condition: the animal an event row names is not DECEASED.

    Vaccination / breeding rows carry no health status of their own, so a
    reminder about an animal that has since died (a MORTALITY vital event
    sets its health_status to DECEASED) must look the animal up. Matched the
    same way domain_validation_utils.animal_identified_by does: the event's
    `ear_tag_id` names either the animal's ear tag or its secondary
    identifier, under the same parent Livestock record.
    """
    return f"""NOT EXISTS (
        SELECT 1 FROM g2p_register_animals dead
        WHERE dead.link_internal_record_id = {event_alias}.link_internal_record_id
          AND (dead.ear_tag_id = {event_alias}.ear_tag_id
               OR dead.secondary_identifier = {event_alias}.ear_tag_id)
          AND dead.health_status = 'DECEASED'
    )"""


def ensure_tracking_table(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text(_TRACKING_TABLE_DDL))


def already_sent(engine: Engine, reminder_type: str, record_internal_id: str, reminder_key: str) -> bool:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT 1 FROM g2p_reminder_emails_sent "
                "WHERE reminder_type = :t AND record_internal_id = :r AND reminder_key = :k"
            ),
            {"t": reminder_type, "r": record_internal_id, "k": str(reminder_key)},
        ).first()
    return row is not None


def record_sent(
    engine: Engine, reminder_type: str, record_internal_id: str, reminder_key: str, recipients: list[str],
) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO g2p_reminder_emails_sent
                    (reminder_type, record_internal_id, reminder_key, recipients)
                VALUES (:t, :r, :k, :rc)
                ON CONFLICT (reminder_type, record_internal_id, reminder_key) DO NOTHING
            """),
            {"t": reminder_type, "r": record_internal_id, "k": str(reminder_key), "rc": ",".join(recipients)},
        )


def resolve_recipients(fallback_env_var: str, district_env_var: str | None = None, district: str | None = None) -> list[str]:
    """Recipients for a reminder email. No per-district/per-user contact
    directory exists in gen2 yet (gen1 matched `res.users` by
    kebele/woreda/zone/region group membership) — so this comes from env
    config instead, same shape `outbreak_alert_service._resolve_recipients`
    already uses:
      - `<district_env_var>`: optional per-district overrides,
        "<district>:<email>[|<email>...];<district>:<email>..."
      - `<fallback_env_var>`: comma-separated list used when no
        district-specific entry matches (or no district applies).
    """
    fallback = [e.strip() for e in os.getenv(fallback_env_var, "").split(",") if e.strip()]
    if district_env_var and district:
        mapping_raw = os.getenv(district_env_var, "")
        for entry in mapping_raw.split(";"):
            entry = entry.strip()
            if not entry or ":" not in entry:
                continue
            name, emails = entry.split(":", 1)
            if name.strip().lower() == district.strip().lower():
                specific = [e.strip() for e in emails.split("|") if e.strip()]
                return specific or fallback
    return fallback


def send_email(subject: str, body: str, recipients: list[str]) -> bool:
    """Send one plain-text email over the registry's shared SMTP relay
    (same OUTBREAK_ALERT_SMTP_* env vars outbreak_alert_service.py uses —
    one mail relay, reused by every reminder type)."""
    if not recipients:
        _logger.warning("Email '%s' has no configured recipients — not sent.", subject)
        return False

    host = os.getenv("OUTBREAK_ALERT_SMTP_HOST")
    if not host:
        _logger.warning("OUTBREAK_ALERT_SMTP_HOST not set — email '%s' not sent.", subject)
        return False

    port = int(os.getenv("OUTBREAK_ALERT_SMTP_PORT", "25"))
    username = os.getenv("OUTBREAK_ALERT_SMTP_USERNAME")
    password = os.getenv("OUTBREAK_ALERT_SMTP_PASSWORD")
    use_tls = os.getenv("OUTBREAK_ALERT_SMTP_USE_TLS", "false").lower() == "true"
    sender = os.getenv("OUTBREAK_ALERT_FROM_EMAIL", "no-reply@livestock-registry.local")

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)

    try:
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            if use_tls:
                smtp.starttls()
            if username and password:
                smtp.login(username, password)
            smtp.sendmail(sender, recipients, msg.as_string())
    except Exception:
        _logger.exception("Failed to send email '%s'", subject)
        return False

    _logger.info("Email sent: '%s' -> %s", subject, recipients)
    return True


def today() -> date:
    return date.today()
