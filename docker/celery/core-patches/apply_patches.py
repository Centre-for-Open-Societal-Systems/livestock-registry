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

# ─── Fix: an ingested submission finalized with no approval workflow was
# indistinguishable from one awaiting approvers. finalize_submission_with_session
# returns quietly when AWE is disabled on the worker, so a misconfigured worker
# left every ODK record FINAL / PENDING with no task for anyone. When the
# submission's form has an intake approval policy, a finalized submission
# must now carry its AWE request; otherwise the ingestion fails with a clear
# reason (and is retried like any other failure), and nothing is committed.
# Forms with no intake policy are not affected.
apply(
    f"{WORKER_BASE}/tasks/ingest_data_worker.py",
    """        bearer_token=await _awe_service_token(),
    )
""",
    """        bearer_token=await _awe_service_token(),
    )
    await _require_approval_workflow(submission_id, session)


async def _require_approval_workflow(submission_id: str, session) -> None:
    \"\"\"Fail the ingestion when the submission's form needs approval but
    finalizing started no AWE request.\"\"\"
    from openg2p_registry_core.models.g2p_intake_form import G2PIntakeFormSubmission
    from openg2p_registry_core.services.g2p_awe_integration_service import REGISTRY_INTAKE_FORM_ARTIFACT
    from openg2p_registry_core.services.g2p_awe_policy_configuration_service import (
        G2PAwePolicyConfigurationService,
    )

    submission = await session.get(G2PIntakeFormSubmission, submission_id)
    if submission is None or submission.awe_request_id:
        return
    policy_service = G2PAwePolicyConfigurationService.get_component() or G2PAwePolicyConfigurationService()
    policy = await policy_service.find_effective_policy_configuration(
        session,
        register_id=submission.register_id,
        policy_type=REGISTRY_INTAKE_FORM_ARTIFACT,
        intake_form_id=submission.form_id,
    )
    if policy is None:
        return
    raise ValueError(
        "AWE_WORKFLOW_NOT_STARTED: the form needs approval (policy "
        f"{policy.policy_key}) but no approval request was created. Check "
        "REGISTRY_CELERY_WORKERS_AWE_ENABLED and the worker's AWE token settings."
    )
""",
    "ingest_data_worker.py: an approval-required submission is never finalized without its AWE request",
)

# ─── Fix: every ingested intake showed Created By "system". An ODK
# submission now shows the ODK Central user who sent it, "<name> (ODK)"
# (__system.submitterName); anything else keeps "system". Same helpers as the
# farmer registry's worker patch.
apply(
    f"{WORKER_BASE}/tasks/ingest_data_worker.py",
    """_INGESTION_CREATED_BY = "system"
""",
    """_INGESTION_CREATED_BY = "system"


def _odk_submitter(incoming_enriched_transformed_data):
    \"\"\"The ODK Central user who sent the submission (__system.submitterName).\"\"\"
    data = incoming_enriched_transformed_data.enriched_data_json
    if isinstance(data, str):
        try:
            import json

            data = json.loads(data)
        except ValueError:
            return None
    for _ in range(4):
        if not isinstance(data, dict):
            return None
        system = data.get("__system")
        if isinstance(system, dict):
            name = (system.get("submitterName") or "").strip()
            return name or None
        data = data.get("body") or data.get("message") or data.get("payload")
    return None


def _ingestion_created_by(incoming_classified_data):
    \"\"\"Who the intake shows as its creator: the ODK user, else the platform default.\"\"\"
    submitter = getattr(incoming_classified_data, "_odk_submitter", None)
    return f"{submitter} (ODK)" if submitter else _INGESTION_CREATED_BY
""",
    "ingest_data_worker.py: helpers for the ODK submitter as Created By",
)
apply(
    f"{WORKER_BASE}/tasks/ingest_data_worker.py",
    """                raise ValueError(f"Incoming transformed data not found for ingest_id '{ingest_id}'")
""",
    """                raise ValueError(f"Incoming transformed data not found for ingest_id '{ingest_id}'")
            incoming_classified_data._odk_submitter = _odk_submitter(incoming_enriched_transformed_data)
""",
    "ingest_data_worker.py: remember who sent the ODK submission",
)
apply(
    f"{WORKER_BASE}/tasks/ingest_data_worker.py",
    """        section_payloads=None,
        created_by=_INGESTION_CREATED_BY,
""",
    """        section_payloads=None,
        created_by=_ingestion_created_by(incoming_classified_data),
""",
    "ingest_data_worker.py: the intake's Created By is the ODK user",
)
apply(
    f"{WORKER_BASE}/tasks/ingest_data_worker.py",
    """            register_id=incoming_classified_data.register_id,
            created_by=_INGESTION_CREATED_BY,
            session=session,
""",
    """            register_id=incoming_classified_data.register_id,
            created_by=_ingestion_created_by(incoming_classified_data),
            session=session,
""",
    "ingest_data_worker.py: sections saved by the ODK user too",
)

# ─── File Import: one Livestock record per farmer, not one per row. The
# livestock import template has one row per animal; the worker sent every
# row to ingestion on its own, so a farmer with three animals became three
# separate records. Rows that name the same farmer (Farmer ID, else Fayda
# FAN ID) are now merged into one record whose `livestock` list holds every
# animal (the shape ls_odk_transform.j2 reads); the farmer and location
# columns come from the first row that fills them. Excel date cells, which
# arrive as "YYYY-MM-DD 00:00:00", are cut back to the date. Files without
# both farmer and animal columns are left exactly as parsed.
apply(
    f"{WORKER_BASE}/tasks/import_file_process_worker.py",
    """            all_records = parse_file_to_records(
                file_content, catalog_doc.source_filename
            )
""",
    """            all_records = parse_file_to_records(
                file_content, catalog_doc.source_filename
            )
            all_records = _group_livestock_rows(all_records)
""",
    "import_file_process_worker.py: group a farmer's animal rows into one record",
)
apply(
    f"{WORKER_BASE}/tasks/import_file_process_worker.py",
    """def parse_file_to_records(file_content: bytes, filename: str) -> list[dict[str, Any]]:
""",
    """_LIVESTOCK_ANIMAL_COLUMNS = (
    "ear_tag_id", "secondary_identifier", "species", "breed", "colour", "weight",
    "quantity", "gender", "date_of_birth", "age", "health_status",
    "vaccination_status", "registration_date",
)


def _group_livestock_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    \"\"\"Merge the animal rows of one farmer into one record with a `livestock` list.\"\"\"
    import re

    if not records:
        return records
    columns = set(records[0].keys())
    if not ({"farmer_id", "fayda_fan_id"} & columns) or not ({"ear_tag_id", "species"} & columns):
        return records
    date_only = re.compile(r"^(\\d{4}-\\d{2}-\\d{2})[ T]00:00:00$")

    def blank(value):
        return value is None or str(value).strip() == ""

    grouped: list[dict[str, Any]] = []
    by_farmer: dict[str, dict[str, Any]] = {}
    for row in records:
        row = {k: (date_only.sub(r"\\1", v.strip()) if isinstance(v, str) else v) for k, v in row.items()}
        animal = {c: row[c] for c in _LIVESTOCK_ANIMAL_COLUMNS if c in row and not blank(row[c])}
        holding = {k: v for k, v in row.items() if k not in _LIVESTOCK_ANIMAL_COLUMNS}
        key = str(row.get("farmer_id") or row.get("fayda_fan_id") or "").strip().upper()
        target = by_farmer.get(key) if key else None
        if target is None:
            target = dict(holding)
            target["livestock"] = []
            grouped.append(target)
            if key:
                by_farmer[key] = target
        for k, v in holding.items():
            if blank(target.get(k)) and not blank(v):
                target[k] = v
        if animal:
            target["livestock"].append(animal)
    _logger.info("File import: %s row(s) grouped into %s record(s)", len(records), len(grouped))
    return grouped


def parse_file_to_records(file_content: bytes, filename: str) -> list[dict[str, Any]]:
""",
    "import_file_process_worker.py: helper that groups livestock rows by farmer",
)

print("ALL PATCHES APPLIED")
