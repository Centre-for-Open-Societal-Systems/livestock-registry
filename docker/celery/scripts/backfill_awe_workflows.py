"""Attach the missing approval workflow to finalized intakes that have none.

Until the ingest worker had AWE settings and a service-account token, every
submission it finalized (ODK, File Import) was left FINAL / PENDING with no
AWE request, so no approver ever got a task. The fixed worker only helps new
submissions; this script repairs the old ones.

Run it in the celery worker pod, which has the worker's database, AWE and
token settings (the image carries it at /app/scripts):

    python3 /app/scripts/backfill_awe_workflows.py
    python3 /app/scripts/backfill_awe_workflows.py --apply
    python3 /app/scripts/backfill_awe_workflows.py --apply --submission-id <id>

It is a plain file, not part of the livestock extension package, on purpose:
the worker's own settings must be created before the extension loads (see
_create_app_settings_first in the extension's __init__). Importing it as a
module of the extension loads the extension first, and AWE then reads empty
core settings (AWE disabled), so no request would ever be created.

Without --apply nothing is changed: every candidate is listed with what would
happen to it. A candidate is an intake that is FINAL, approval PENDING, has
no AWE request, and whose form has an intake approval policy. By default only
PARTNER (ODK / File Import) intakes are considered; --all-sources adds staff
entries.

Per candidate:

- SOURCE: the ingestion message the intake came from. Several intakes from
  one message are DUPLICATE and are only listed: which one is the real record
  is a team decision, then that one is processed with --submission-id.
  An intake with no linked message is processed only with --submission-id.
- VALIDATE: every section is checked again with the rules a staff save runs
  (coded values and the livestock domain rules). These intakes may have been
  saved while a since-fixed bug skipped validation; an INVALID one is listed
  with the reason and left alone.
- APPLY: the submission is finalized again through the platform's own
  finalize_submission_with_session with the worker's service token, which
  starts its AWE request. AWE keys the request by the submission
  ("intake-<submission_id>"), so a request that already exists is reused,
  and running the script twice creates nothing twice.

Each submission is committed on its own; one failure does not stop the rest.
Records whose AWE decision never reached the registry (callback refused) are
a different repair: retry those deliveries from AWE's admin API
(POST /v1/awe/admin/deliveries/{id}/retry) once the staff API is fixed.
"""

import argparse
import asyncio
import sys
from collections import defaultdict


def _bootstrap():
    """Start the platform the way the celery worker does: extension aliasing,
    settings, components, and the livestock ingest hooks."""
    import importlib

    import openg2p_registry_celery_worker.main  # noqa: F401

    # By module path: the tasks package exports a celery task of the same name.
    return importlib.import_module("openg2p_registry_celery_worker.tasks.ingest_data_worker")


async def _candidates(session, all_sources: bool, submission_id: str | None):
    from openg2p_registry_core.models import IncomingClassifiedData, IncomingRawData
    from openg2p_registry_core.models.g2p_intake_form import G2PIntakeFormSubmission
    from sqlalchemy import select

    query = select(G2PIntakeFormSubmission).where(
        G2PIntakeFormSubmission.draft_status == "FINAL",
        G2PIntakeFormSubmission.approval_status == "PENDING",
        G2PIntakeFormSubmission.awe_request_id.is_(None),
    )
    if submission_id:
        query = query.where(G2PIntakeFormSubmission.submission_id == submission_id)
    elif not all_sources:
        query = query.where(G2PIntakeFormSubmission.submission_source == "PARTNER")
    submissions = (await session.execute(query.order_by(G2PIntakeFormSubmission.first_created_at))).scalars().all()

    source_rows = (
        await session.execute(
            select(IncomingClassifiedData.intake_form_submission_id, IncomingRawData.ingest_message_id).join(
                IncomingRawData, IncomingRawData.ingest_id == IncomingClassifiedData.ingest_id
            )
        )
    ).all()
    message_of = {str(sub_id): msg for sub_id, msg in source_rows if sub_id}
    return submissions, message_of


async def _needs_approval(session, submission) -> str | None:
    from openg2p_registry_core.services.g2p_awe_integration_service import REGISTRY_INTAKE_FORM_ARTIFACT
    from openg2p_registry_core.services.g2p_awe_policy_configuration_service import (
        G2PAwePolicyConfigurationService,
    )

    policy = await G2PAwePolicyConfigurationService.get_component().find_effective_policy_configuration(
        session,
        register_id=submission.register_id,
        policy_type=REGISTRY_INTAKE_FORM_ARTIFACT,
        intake_form_id=submission.form_id,
    )
    return policy.policy_key if policy else None


async def _validation_error(session, submission) -> str | None:
    """None when every section passes the checks a staff save runs."""
    from openg2p_registry_core.interfaces import G2PRegisterDomainFactory
    from openg2p_registry_core.services import G2PAttributeValueValidator, G2PIntakeFormDataService

    service = G2PIntakeFormDataService.get_component()
    domain_factory = G2PRegisterDomainFactory.get_component() or G2PRegisterDomainFactory()
    for item in await service._build_section_payloads(submission, session):
        records = [r for r in (item.records or []) if isinstance(r, dict)]
        if not records:
            continue
        section = await service._get_section_or_error(item.section_id, session)
        definition = await service._get_register_definition(item.section_register_id, session)
        try:
            await G2PAttributeValueValidator.get_component().validate_records(
                records,
                field_map=G2PAttributeValueValidator.field_map_from_ui_schema(section.section_ui_schema),
            )
            domain_service = domain_factory.get_domain_service(definition.register_mnemonic)
            if domain_service:
                await domain_service.validate_domain_attributes(records)
        except Exception as error:
            message = getattr(error, "message", None) or str(error)
            return f"{section.section_mnemonic}: {message}"
    return None


async def _run(args) -> int:
    worker = _bootstrap()
    from openg2p_registry_core.services import G2PIntakeFormDataService

    from openg2p_registry_livestock_extension.register_domain.services.domain_validation_utils import (
        ingest_session,
    )

    from openg2p_registry_celery_worker.engine import Engine

    session_maker = Engine.get_async_session_maker()

    async with session_maker() as session:
        submissions, message_of = await _candidates(session, args.all_sources, args.submission_id)
        per_message = defaultdict(list)
        for submission in submissions:
            per_message[message_of.get(str(submission.submission_id))].append(submission.submission_id)
        plan = []
        for submission in submissions:
            policy_key = await _needs_approval(session, submission)
            if policy_key is None:
                continue
            message = message_of.get(str(submission.submission_id))
            if args.submission_id:
                status = "SELECTED"
            elif message is None:
                status = "NO_SOURCE"
            elif len(per_message[message]) > 1:
                status = "DUPLICATE"
            else:
                status = "READY"
            plan.append((submission.submission_id, submission.application_reference, message, policy_key, status))

    print(f"{len(plan)} finalized intake(s) without an approval workflow")
    if not plan:
        return 0

    token = await worker._awe_service_token() if args.apply else None
    if args.apply and not token:
        print("No AWE service token: set REGISTRY_CELERY_WORKERS_AWE_TOKEN_URL / _CLIENT_ID / _CLIENT_SECRET")
        return 2

    failures = 0
    for submission_id, reference, message, policy_key, status in plan:
        line = f"{submission_id} | {reference} | source={message or '-'} | policy={policy_key}"
        if status in ("NO_SOURCE", "DUPLICATE"):
            print(f"SKIP {status:9} {line}  (process with --submission-id once decided)")
            continue
        async with session_maker() as session:
            from openg2p_registry_core.models.g2p_intake_form import G2PIntakeFormSubmission

            submission = await session.get(G2PIntakeFormSubmission, submission_id)
            reset = ingest_session.set(session)
            try:
                error = await _validation_error(session, submission)
            finally:
                ingest_session.reset(reset)
            if error:
                print(f"SKIP INVALID   {line}  ({error})")
                continue
            if not args.apply:
                print(f"WOULD ATTACH   {line}")
                continue
            try:
                await G2PIntakeFormDataService.get_component().finalize_submission_with_session(
                    submission_id, session, bearer_token=token
                )
                await session.flush()
                if not submission.awe_request_id:
                    raise RuntimeError("finalize returned without an AWE request")
                await session.commit()
                print(f"ATTACHED       {line} | awe_request={submission.awe_request_id}")
            except Exception as error:
                await session.rollback()
                failures += 1
                print(f"FAILED         {line}  ({getattr(error, 'message', None) or error})")
    return 1 if failures else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--apply", action="store_true", help="attach workflows (default: only list)")
    parser.add_argument("--submission-id", help="process only this submission (also a DUPLICATE or NO_SOURCE one)")
    parser.add_argument("--all-sources", action="store_true", help="include staff entries, not only PARTNER")
    args = parser.parse_args(argv)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
