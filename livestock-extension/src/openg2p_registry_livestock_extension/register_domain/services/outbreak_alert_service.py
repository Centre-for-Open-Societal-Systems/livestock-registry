"""Notifiable-disease outbreak alert.

3+ notifiable-disease cases of the *same* disease, in the *same* district
(woreda), within a rolling 14-day window -> automatic alert email to the
district/regional vet officers. Mirrors gen1's
`g2p.livestock.health.event._check_outbreak()` /
`mail_template_outbreak_alert` (g2p_livestock_registry/models/livestock_event.py),
re-implemented for gen2's headless FastAPI/Celery stack, which has no
mail.thread/mail.template and no per-district vet-officer directory.

Kept as plain, directly-callable functions (not celery-task-shaped) for the
same reason audit_retention_service is: callable from the scheduled
celery-beat task (see ../../tasks/outbreak_alert_beat_producer.py) for the
real, periodic sweep, and callable directly (sync, no celery/broker needed)
to test the exact same detection+email logic on demand.

Detection runs as a periodic sweep over the trailing window rather than a
per-record trigger (unlike gen1's `create()` override) because this domain
service's `validate_domain_attributes` hook only fires on the intake-form
save path, not on every path a record can reach the register table (bulk
import, sync) — a sweep also catches a backdated/edited onset date a
create-time check would miss. A small tracking table
(`g2p_outbreak_alerts_sent`, created here directly with `CREATE TABLE IF NOT
EXISTS` rather than relying on SQLAlchemy `create_all()` — new tables do not
reliably auto-create on this stack) records the case count last alerted for
each (disease_type, district) cluster, so re-running the sweep only re-emails
once a cluster has grown past what was already alerted.

Recipients: gen1 resolved "Woreda Approver" / "Regional Vet Officer" by
matching `res.users` against the record's woreda/region. Gen2 has no
equivalent per-district contact directory yet, so recipients come from env
config instead — see `_resolve_recipients` — swap that for a real
per-woreda/region vet-officer lookup once one exists.
"""

import logging
import os
import smtplib
from datetime import date, timedelta
from email.mime.text import MIMEText

from sqlalchemy import text
from sqlalchemy.engine import Engine

_logger = logging.getLogger("g2p-outbreak-alert")

DEFAULT_WINDOW_DAYS = 14
DEFAULT_THRESHOLD = 3

_TRACKING_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS g2p_outbreak_alerts_sent (
    id SERIAL PRIMARY KEY,
    disease_type VARCHAR NOT NULL,
    district VARCHAR NOT NULL,
    case_count INTEGER NOT NULL,
    window_start DATE NOT NULL,
    alerted_at TIMESTAMP NOT NULL DEFAULT now(),
    recipients TEXT,
    UNIQUE (disease_type, district)
)
"""


def ensure_tracking_table(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text(_TRACKING_TABLE_DDL))


def detect_outbreak_clusters(
    engine: Engine,
    window_days: int = DEFAULT_WINDOW_DAYS,
    threshold: int = DEFAULT_THRESHOLD,
    as_of: date | None = None,
) -> list[dict]:
    """Every (disease_type, district) cluster with >= `threshold` notifiable
    cases whose date_onset falls in the trailing `window_days` days up to
    `as_of` (defaults to today). `district` is the livestock holding's
    woreda, joined in via `health_event.link_internal_record_id ->
    livestock.internal_record_id` (health events carry no admin-area
    columns of their own — see register_domain/models/admin_area.py).
    """
    as_of = as_of or date.today()
    window_start = as_of - timedelta(days=window_days)

    query = text("""
        SELECT
            he.disease_type AS disease_type,
            ls.woreda AS district,
            ls.region AS region,
            COUNT(*) AS case_count,
            MAX(he.date_onset) AS most_recent_onset,
            (ARRAY_AGG(he.ear_tag_id ORDER BY he.date_onset DESC))[1] AS most_recent_ear_tag
        FROM g2p_register_health_events he
        JOIN g2p_register_livestocks ls
            ON ls.internal_record_id = he.link_internal_record_id
        WHERE he.is_notifiable IS TRUE
          AND he.disease_type IS NOT NULL AND he.disease_type <> ''
          AND he.date_onset >= :window_start
          AND he.date_onset <= :as_of
          AND he.record_status = 'ACTIVE'
          AND ls.woreda IS NOT NULL AND ls.woreda <> ''
        GROUP BY he.disease_type, ls.woreda, ls.region
        HAVING COUNT(*) >= :threshold
        ORDER BY case_count DESC
    """)

    with engine.connect() as conn:
        rows = conn.execute(
            query,
            {"window_start": window_start, "as_of": as_of, "threshold": threshold},
        ).mappings().all()

    return [
        {
            "disease_type": row["disease_type"],
            "district": row["district"],
            "region": row["region"],
            "case_count": row["case_count"],
            "window_start": window_start,
            "most_recent_onset": row["most_recent_onset"],
            "most_recent_ear_tag": row["most_recent_ear_tag"],
        }
        for row in rows
    ]


def _already_alerted(engine: Engine, disease_type: str, district: str, case_count: int) -> bool:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT case_count FROM g2p_outbreak_alerts_sent "
                "WHERE disease_type = :d AND district = :w"
            ),
            {"d": disease_type, "w": district},
        ).first()
    return row is not None and row[0] >= case_count


def _record_alert(
    engine: Engine, disease_type: str, district: str, case_count: int,
    window_start: date, recipients: list[str],
) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO g2p_outbreak_alerts_sent
                    (disease_type, district, case_count, window_start, recipients)
                VALUES (:d, :w, :c, :ws, :r)
                ON CONFLICT (disease_type, district) DO UPDATE
                    SET case_count = EXCLUDED.case_count,
                        window_start = EXCLUDED.window_start,
                        alerted_at = now(),
                        recipients = EXCLUDED.recipients
            """),
            {"d": disease_type, "w": district, "c": case_count, "ws": window_start,
             "r": ",".join(recipients)},
        )


def _resolve_recipients(district: str) -> list[str]:
    """District/regional vet officer email(s) for `district`.

    No per-district vet-officer directory exists yet in gen2 (gen1's
    region-scoped `res.users` lookup has no equivalent here), so recipients
    come from env config:
      - OUTBREAK_ALERT_DISTRICT_EMAILS: optional per-district overrides,
        "<district>:<email>[|<email>...];<district>:<email>...", e.g.
        "Ada'a:vet.adaa@moa.gov.et|regional.oromia@moa.gov.et"
      - OUTBREAK_ALERT_FALLBACK_EMAILS: comma-separated list used whenever no
        district-specific entry matches.
    """
    fallback = [e.strip() for e in os.getenv("OUTBREAK_ALERT_FALLBACK_EMAILS", "").split(",") if e.strip()]
    mapping_raw = os.getenv("OUTBREAK_ALERT_DISTRICT_EMAILS", "")
    for entry in mapping_raw.split(";"):
        entry = entry.strip()
        if not entry or ":" not in entry:
            continue
        name, emails = entry.split(":", 1)
        if name.strip().lower() == district.strip().lower():
            specific = [e.strip() for e in emails.split("|") if e.strip()]
            return specific or fallback
    return fallback


def _send_alert_email(cluster: dict, recipients: list[str]) -> bool:
    if not recipients:
        _logger.warning(
            "Outbreak alert for %s in %s (%d cases) has no configured recipients — "
            "set OUTBREAK_ALERT_DISTRICT_EMAILS or OUTBREAK_ALERT_FALLBACK_EMAILS.",
            cluster["disease_type"], cluster["district"], cluster["case_count"],
        )
        return False

    host = os.getenv("OUTBREAK_ALERT_SMTP_HOST")
    if not host:
        _logger.warning("OUTBREAK_ALERT_SMTP_HOST not set — outbreak alert email not sent.")
        return False

    port = int(os.getenv("OUTBREAK_ALERT_SMTP_PORT", "25"))
    username = os.getenv("OUTBREAK_ALERT_SMTP_USERNAME")
    password = os.getenv("OUTBREAK_ALERT_SMTP_PASSWORD")
    use_tls = os.getenv("OUTBREAK_ALERT_SMTP_USE_TLS", "false").lower() == "true"
    sender = os.getenv("OUTBREAK_ALERT_FROM_EMAIL", "no-reply@livestock-registry.local")

    subject = f"⚠ Possible outbreak: {cluster['disease_type']} in {cluster['district']}"
    body = (
        f"{cluster['case_count']} notifiable disease cases of {cluster['disease_type']} "
        f"have been recorded in {cluster['district']}"
        + (f", {cluster['region']}" if cluster.get("region") else "")
        + f" within the last {DEFAULT_WINDOW_DAYS} days (since {cluster['window_start']}).\n\n"
        f"Most recent case: ear tag {cluster.get('most_recent_ear_tag') or '-'} "
        f"on {cluster.get('most_recent_onset')}.\n\n"
        "This may indicate a disease outbreak and needs review.\n\n"
        "This is an automated alert from the Livestock Registry."
    )
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
        _logger.exception(
            "Failed to send outbreak alert email for %s in %s",
            cluster["disease_type"], cluster["district"],
        )
        return False

    _logger.info(
        "Outbreak alert sent: %s in %s (%d cases) -> %s",
        cluster["disease_type"], cluster["district"], cluster["case_count"], recipients,
    )
    return True


def check_and_alert_outbreaks(
    engine: Engine,
    window_days: int = DEFAULT_WINDOW_DAYS,
    threshold: int = DEFAULT_THRESHOLD,
    as_of: date | None = None,
) -> list[dict]:
    """Run one detection sweep: email any cluster that is new or has grown
    since it was last alerted, and record what was sent. Returns the
    clusters that actually triggered an email this run (empty list if
    nothing new).
    """
    ensure_tracking_table(engine)
    clusters = detect_outbreak_clusters(engine, window_days, threshold, as_of)

    alerted = []
    for cluster in clusters:
        if _already_alerted(engine, cluster["disease_type"], cluster["district"], cluster["case_count"]):
            continue

        recipients = _resolve_recipients(cluster["district"])
        sent = _send_alert_email(cluster, recipients)
        if sent:
            _record_alert(
                engine, cluster["disease_type"], cluster["district"],
                cluster["case_count"], cluster["window_start"], recipients,
            )
            alerted.append(cluster)
        # else: leave untracked so the next sweep retries once recipients/SMTP are fixed.

    return alerted
