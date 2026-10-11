"""Applies patches to this image's installed openg2p_registry_celery_beat AND
openg2p_registry_celery_worker packages at build time (both live in the same
shared celery image — see docker/celery/Dockerfile):
  - audit-log retention — G2R-135's "7-year retention period" requirement.
  - notifiable-disease outbreak alert — 3+ cases of the same disease in the
    same district within 14 days -> alert email to vet officers.
  - vaccination due-soon / overdue reminder emails.
  - approval-pending-too-long reminder emails.
  - upcoming-birth (calving) reminder emails.
  - intake_form_register_ingest_worker: deterministic row processing order
    (was unordered) — see the patch below for why this matters.

Same technique as docker/staff-api/core-patches/apply_patches.py and the same
reason: celery-beat's task registry and beat_schedule are both hardcoded in
its own installed package, with no extension hook for a domain package to
add a scheduled task of its own — so this is a minimal, exact-match patch
rather than a wholesale file replacement, applied at every build so it
survives rebuilds instead of being silently lost.

Run at Docker build time only (see docker/celery/Dockerfile).
"""

BASE = "/usr/local/lib/python3.12/site-packages/openg2p_registry_celery_beat"
WORKER_BASE = "/usr/local/lib/python3.12/site-packages/openg2p_registry_celery_worker"


def apply(path, old, new, label):
    with open(path) as f:
        content = f.read()
    n = content.count(old)
    assert n == 1, f"{label}: expected 1 match in {path}, found {n}"
    content = content.replace(old, new)
    with open(path, "w") as f:
        f.write(content)
    print(f"OK: {label}")


# ─── Register the livestock extension's audit-log-retention task alongside
# celery-beat's own producers, so `include=["openg2p_registry_celery_beat.tasks"]`
# picks it up too.
apply(
    f"{BASE}/tasks/__init__.py",
    '''from .import_file_process_beat_producer import import_file_process_beat_producer''',
    '''from .import_file_process_beat_producer import import_file_process_beat_producer
from openg2p_registry_livestock_extension.tasks.audit_log_retention_beat_producer import (
    audit_log_retention_beat_producer,
)''',
    "tasks/__init__.py: register audit_log_retention_beat_producer",
)

# ─── Schedule it — once a day. A housekeeping job, not high-frequency data
# pipeline work like the producers above it, so a fixed interval rather than
# a new Settings field is enough here.
# Anchored on the schedule dict's last entry, which registry-platform 1.2 made
# register_export_beat_producer.
apply(
    f"{BASE}/app.py",
    '''    "register_export_beat_producer": {
        "task": "register_export_beat_producer",
        "schedule": (
            _config.register_export_beat_producer_frequency
            or _config.default_beat_producer_frequency
        ),
    },
}
celery_app.conf.timezone = "UTC"''',
    '''    "register_export_beat_producer": {
        "task": "register_export_beat_producer",
        "schedule": (
            _config.register_export_beat_producer_frequency
            or _config.default_beat_producer_frequency
        ),
    },
    "audit_log_retention_beat_producer": {
        "task": "audit_log_retention_beat_producer",
        "schedule": 86400.0,  # once a day
    },
}
celery_app.conf.timezone = "UTC"''',
    "app.py: schedule audit_log_retention_beat_producer daily",
)

# ─── Register the livestock extension's outbreak-alert task, chaining off the
# audit-log-retention registration this same script just applied above (not
# the pristine base file — see the module docstring).
apply(
    f"{BASE}/tasks/__init__.py",
    '''from openg2p_registry_livestock_extension.tasks.audit_log_retention_beat_producer import (
    audit_log_retention_beat_producer,
)''',
    '''from openg2p_registry_livestock_extension.tasks.audit_log_retention_beat_producer import (
    audit_log_retention_beat_producer,
)
from openg2p_registry_livestock_extension.tasks.outbreak_alert_beat_producer import (
    outbreak_alert_beat_producer,
)''',
    "tasks/__init__.py: register outbreak_alert_beat_producer",
)

# ─── Schedule it — every 15 minutes. Detects a growing disease cluster and
# emails district/regional vet officers close to when it crosses the
# 3-cases-in-14-days threshold, without hammering the DB like a high-frequency
# data-pipeline producer would need to.
apply(
    f"{BASE}/app.py",
    '''    "audit_log_retention_beat_producer": {
        "task": "audit_log_retention_beat_producer",
        "schedule": 86400.0,  # once a day
    },
}
celery_app.conf.timezone = "UTC"''',
    '''    "audit_log_retention_beat_producer": {
        "task": "audit_log_retention_beat_producer",
        "schedule": 86400.0,  # once a day
    },
    "outbreak_alert_beat_producer": {
        "task": "outbreak_alert_beat_producer",
        "schedule": 900.0,  # every 15 minutes
    },
}
celery_app.conf.timezone = "UTC"''',
    "app.py: schedule outbreak_alert_beat_producer every 15 minutes",
)

# ─── Register the three reminder-email tasks, chaining off the
# outbreak-alert registration this same script just applied above.
apply(
    f"{BASE}/tasks/__init__.py",
    '''from openg2p_registry_livestock_extension.tasks.outbreak_alert_beat_producer import (
    outbreak_alert_beat_producer,
)''',
    '''from openg2p_registry_livestock_extension.tasks.outbreak_alert_beat_producer import (
    outbreak_alert_beat_producer,
)
from openg2p_registry_livestock_extension.tasks.vaccination_reminder_beat_producer import (
    vaccination_reminder_beat_producer,
)
from openg2p_registry_livestock_extension.tasks.approval_pending_reminder_beat_producer import (
    approval_pending_reminder_beat_producer,
)
from openg2p_registry_livestock_extension.tasks.calving_reminder_beat_producer import (
    calving_reminder_beat_producer,
)''',
    "tasks/__init__.py: register the three reminder-email beat producers",
)

# ─── Schedule them — once a day (housekeeping-style reminders, not
# high-frequency data-pipeline work; a record only needs to be checked once
# per day for "is it now due/overdue/stuck/soon").
apply(
    f"{BASE}/app.py",
    '''    "outbreak_alert_beat_producer": {
        "task": "outbreak_alert_beat_producer",
        "schedule": 900.0,  # every 15 minutes
    },
}
celery_app.conf.timezone = "UTC"''',
    '''    "outbreak_alert_beat_producer": {
        "task": "outbreak_alert_beat_producer",
        "schedule": 900.0,  # every 15 minutes
    },
    "vaccination_reminder_beat_producer": {
        "task": "vaccination_reminder_beat_producer",
        "schedule": 86400.0,  # once a day
    },
    "approval_pending_reminder_beat_producer": {
        "task": "approval_pending_reminder_beat_producer",
        "schedule": 86400.0,  # once a day
    },
    "calving_reminder_beat_producer": {
        "task": "calving_reminder_beat_producer",
        "schedule": 86400.0,  # once a day
    },
}
celery_app.conf.timezone = "UTC"''',
    "app.py: schedule the three reminder-email beat producers daily",
)

# ─── Fix: intake_form_register_ingest_worker processed a submission's intake
# rows in WHATEVER order Postgres happened to return them (no ORDER BY), not
# insertion order. Harmless for most sections, but a real bug for one like
# Health Event where post_ingest side effects (our health_status sync) are
# order-sensitive: a Disease row and a Recovery row added to the same
# submission could apply in either order, sometimes leaving the animal
# stuck SICK even though Recovery was the row added (chronologically) last.
# Ordering by created_at makes the same-submission processing order match
# the order the rows were actually added in — a general correctness fix,
# not specific to the livestock extension, so every section benefits.
apply(
    f"{WORKER_BASE}/tasks/intake_form_register_ingest_worker.py",
    '''async def _get_intake_rows(intake_class, submission_id: str, session) -> list[object]:
    return (
        await session.execute(select(intake_class).where(intake_class.submission_id == submission_id))
    ).scalars().all()''',
    '''async def _get_intake_rows(intake_class, submission_id: str, session) -> list[object]:
    return (
        await session.execute(
            select(intake_class)
            .where(intake_class.submission_id == submission_id)
            .order_by(intake_class.created_at.asc(), intake_class.internal_record_id.asc())
        )
    ).scalars().all()''',
    "intake_form_register_ingest_worker.py: process a submission's intake rows in creation order",
)

# ─── Fix: an ingested (ODK / partner) submission's approval workflow never
# started. ingest_data_worker finalizes the submission it saved, and
# finalize_submission_with_session starts the AWE approval request for it —
# but the worker passed no bearer token (a worker has no logged-in user), so
# AWE refused with AWE_BEARER_TOKEN_REQUIRED or, with AWE disabled on the
# worker, the submission was finalized with no approval request at all: FINAL
# and PENDING forever, with no task for any approver. A staff "Submit" sends
# the user's token; the worker now sends a client-credentials token of its
# own Keycloak client (REGISTRY_CELERY_WORKERS_AWE_CLIENT_ID, a client with
# Service accounts enabled), the same way the farmer registry's worker does.
# Unset settings leave the old behaviour (no token), so a deployment that
# has not configured the client is not broken by this patch, only unchanged.
apply(
    f"{WORKER_BASE}/tasks/ingest_data_worker.py",
    '''async def _finalize_submission_async(submission_id: str, session) -> None:
    await G2PIntakeFormDataService.get_component().finalize_submission_with_session(
        submission_id,
        session,
    )''',
    '''async def _finalize_submission_async(submission_id: str, session) -> None:
    await G2PIntakeFormDataService.get_component().finalize_submission_with_session(
        submission_id,
        session,
        bearer_token=await _awe_service_token(),
    )


_awe_token_cache: dict = {}


async def _awe_service_token() -> str | None:
    """Client-credentials token the ingested submission's approval workflow is
    started with (REGISTRY_CELERY_WORKERS_AWE_TOKEN_URL / _CLIENT_ID /
    _CLIENT_SECRET). None when those are unset. Cached until shortly before
    it expires. REGISTRY_CELERY_WORKERS_AWE_TOKEN_ISSUER_BASE_URL, when set,
    is presented as X-Forwarded-* so a token fetched over Keycloak's
    in-cluster address still carries the public issuer AWE trusts."""
    import os
    import time

    import httpx

    token_url = os.environ.get("REGISTRY_CELERY_WORKERS_AWE_TOKEN_URL")
    client_id = os.environ.get("REGISTRY_CELERY_WORKERS_AWE_CLIENT_ID")
    client_secret = os.environ.get("REGISTRY_CELERY_WORKERS_AWE_CLIENT_SECRET")
    if not (token_url and client_id and client_secret):
        return None
    if _awe_token_cache.get("expires_at", 0) > time.time() + 30:
        return _awe_token_cache["token"]
    headers = {}
    issuer_base = os.environ.get("REGISTRY_CELERY_WORKERS_AWE_TOKEN_ISSUER_BASE_URL")
    if issuer_base:
        from urllib.parse import urlsplit

        public = urlsplit(issuer_base)
        headers = {
            "X-Forwarded-Host": public.hostname or "",
            "X-Forwarded-Proto": public.scheme or "https",
            "X-Forwarded-Port": str(public.port or (443 if public.scheme != "http" else 80)),
        }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            token_url,
            headers=headers,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
        )
        response.raise_for_status()
        body = response.json()
    _awe_token_cache["token"] = body["access_token"]
    _awe_token_cache["expires_at"] = time.time() + int(body.get("expires_in", 60))
    return body["access_token"]''',
    "ingest_data_worker.py: start the ingested submission's approval workflow with a service-account token",
)

print("ALL PATCHES APPLIED")
