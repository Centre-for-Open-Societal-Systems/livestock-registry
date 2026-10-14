"""Applies our fixes to the base image's installed openg2p_registry_core at
build time — NOT a wholesale file replacement, which is unsafe here: the
image's registry-platform lineage drifts from any local checkout in places
unrelated to these fixes, so overwriting whole files can delete code the base
image needs and crash the app on import. Every patch below finds an exact,
small, known-good substring already proven to match this image's real file
content and swaps in the minimal fix, applied on every build so it survives
rebuilds.

Three fixes remain on registry-platform 1.2: two domain-service hooks the
platform does not have (post_intake_upsert, post_approval_stage with its AWE
stage events) and the CSRF exemption of the approver-resolver endpoint. The
attribute-model patches (cross-attribute parents, per-value vaccine schedules,
per-species config) are gone with the platform's attribute model: code lists
are read from Master Data since 1.2, the species config is a table the
livestock extension owns (register_domain/models/species_config.py) and the
vaccine interval lives in the Vaccine Schedule register.

Run at Docker build time only (see docker/staff-api/Dockerfile and
docker/partner-api/Dockerfile).
"""

import os

BASE = "/usr/local/lib/python3.12/site-packages/openg2p_registry_core"
STAFF_API_MAIN = "/usr/local/lib/python3.12/site-packages/openg2p_registry_staff_api/main.py"


def apply(path, old, new, label):
    with open(path) as f:
        content = f.read()
    n = content.count(old)
    assert n == 1, f"{label}: expected 1 match in {path}, found {n}"
    content = content.replace(old, new)
    with open(path, "w") as f:
        f.write(content)
    print(f"OK: {label}")


# ─── Fix 1: new domain-service extension hook, post_intake_upsert, called
# right after an intake-form section's records are upserted (staff clicking
# "Next"/save on that section) — well before the submission is approved or
# ingested. Added for G2PRegisterDomainServiceVitalEvent to reserve a Birth
# event's offspring ear tag(s) immediately, instead of only once the
# submission is later approved/ingested (see the livestock extension's
# g2p_register_domain_service_vital_event.py for the override).
apply(
    f"{BASE}/services/g2p_register_domain_service.py",
    '''    async def post_ingest(self, register_id: str, register_row, session: AsyncSession):
        pass''',
    '''    async def post_ingest(self, register_id: str, register_row, session: AsyncSession):
        pass

    async def post_intake_upsert(self, rows: list, session: AsyncSession) -> None:
        """Optional extension hook: runs right after an intake-form section's
        records have been upserted (and flushed) into the intake draft table
        -- i.e. when staff click "Next"/save on that section -- well before
        the submission is ever approved or ingested into the live register.
        `rows` are the just-upserted intake-draft ORM rows for that section.
        Override to enrich/mutate those still-draft rows (e.g. reserve an
        identifier ahead of time so it can be shown back to staff
        immediately). No-op by default."""
        pass''',
    "g2p_register_domain_service.py: add post_intake_upsert hook",
)

apply(
    f"{BASE}/services/intake_form_data_service.py",
    # Anchored on the end of the upsert call and the delete that follows it,
    # as registry-platform 1.2 writes them.
    '''            domain_service=domain_service,
        )
        deleted_ids = await self._delete_missing_intake_rows(existing_rows, incoming_ids, session)''',
    '''            domain_service=domain_service,
        )

        if domain_service and incoming_ids:
            upserted_rows = [
                row
                for row in await self._get_intake_rows_list(intake_class, submission.submission_id, session)
                if row.internal_record_id in incoming_ids
            ]
            # Runs while the section is still just an intake draft -- i.e. as
            # soon as staff save/"Next" this section, well before the
            # submission is approved or ingested.
            await domain_service.post_intake_upsert(upserted_rows, session)
            await session.flush()

        deleted_ids = await self._delete_missing_intake_rows(existing_rows, incoming_ids, session)''',
    "intake_form_data_service.py: call post_intake_upsert after section save",
)

# ─── Fix 2: new domain-service extension hook, post_approval_stage, called on
# EVERY approved AWE stage of an intake-form submission's approval chain --
# not just the final one. Without this, a multi-stage policy (e.g. Livestock's
# Kebele -> Woreda -> Zone -> Region hierarchical approval) advances fine
# inside AWE itself, but the registry side has no way to know which stage a
# submission is currently sitting at, since the webhook handler here only
# ever reacted to the 3 TERMINAL_EVENT_TYPES (request_approved/rejected/
# cancelled) and silently ignored every intermediate `stage_completed` event.
# See the livestock extension's g2p_register_domain_service_livestock.py for
# the override that maps stage_order -> LivestockStateEnum.
apply(
    f"{BASE}/services/g2p_register_domain_service.py",
    '''    async def post_intake_upsert(self, rows: list, session: AsyncSession) -> None:
        """Optional extension hook: runs right after an intake-form section's
        records have been upserted (and flushed) into the intake draft table
        -- i.e. when staff click "Next"/save on that section -- well before
        the submission is ever approved or ingested into the live register.
        `rows` are the just-upserted intake-draft ORM rows for that section.
        Override to enrich/mutate those still-draft rows (e.g. reserve an
        identifier ahead of time so it can be shown back to staff
        immediately). No-op by default."""
        pass''',
    '''    async def post_intake_upsert(self, rows: list, session: AsyncSession) -> None:
        """Optional extension hook: runs right after an intake-form section's
        records have been upserted (and flushed) into the intake draft table
        -- i.e. when staff click "Next"/save on that section -- well before
        the submission is ever approved or ingested into the live register.
        `rows` are the just-upserted intake-draft ORM rows for that section.
        Override to enrich/mutate those still-draft rows (e.g. reserve an
        identifier ahead of time so it can be shown back to staff
        immediately). No-op by default."""
        pass

    async def post_approval_stage(
        self, submission, stage_order: int | None, event_type: str, session: AsyncSession
    ) -> None:
        """Optional extension hook: runs once per approved stage of an
        intake-form submission's AWE approval chain -- both for every
        non-final `stage_completed` event (event_type="stage_completed",
        stage_order = the stage that just approved) AND once more for the
        final approval (event_type="request_approved", stage_order = that
        last stage), called BEFORE the submission is marked approved/queued
        for ingest so a field this hook sets on `submission`'s own section
        rows is guaranteed to already be there by the time the async ingest
        worker later copies them into the live register row. A rejected
        stage is never forwarded here -- request_rejected is handled
        separately, unchanged. No-op by default."""
        pass''',
    "g2p_register_domain_service.py: add post_approval_stage hook",
)

apply(
    f"{BASE}/services/g2p_awe_webhook_service.py",
    '''            try:
                if event.event_type in TERMINAL_EVENT_TYPES:
                    await self._apply_terminal_event(event, session)
                log_row.applied = True''',
    '''            try:
                if event.event_type in TERMINAL_EVENT_TYPES:
                    await self._apply_terminal_event(event, session)
                elif event.event_type == "stage_completed":
                    await self._apply_stage_completed_event(event, session)
                log_row.applied = True''',
    "g2p_awe_webhook_service.py: dispatch stage_completed events",
)

apply(
    f"{BASE}/services/g2p_awe_webhook_service.py",
    '''    async def _apply_terminal_event(self, event: AweWebhookEvent, session) -> None:
        if event.artifact_type == REGISTRY_CHANGE_REQUEST_ARTIFACT:
            await self._apply_terminal_event_for_change_request(event, session)
            return
        if event.artifact_type == REGISTRY_INTAKE_FORM_ARTIFACT:
            await self._apply_terminal_event_for_intake_form_submission(event, session)
            return
        raise G2PRegistryException(
            code=G2PRegistryErrorCodes.AWE_WEBHOOK_UNSUPPORTED_ARTIFACT.value[1],
            message=(
                f"{G2PRegistryErrorCodes.AWE_WEBHOOK_UNSUPPORTED_ARTIFACT.value[0]}: "
                f"{event.artifact_type}"
            ),
        )

    async def _apply_terminal_event_for_change_request(''',
    '''    async def _apply_terminal_event(self, event: AweWebhookEvent, session) -> None:
        if event.artifact_type == REGISTRY_CHANGE_REQUEST_ARTIFACT:
            await self._apply_terminal_event_for_change_request(event, session)
            return
        if event.artifact_type == REGISTRY_INTAKE_FORM_ARTIFACT:
            await self._apply_terminal_event_for_intake_form_submission(event, session)
            return
        raise G2PRegistryException(
            code=G2PRegistryErrorCodes.AWE_WEBHOOK_UNSUPPORTED_ARTIFACT.value[1],
            message=(
                f"{G2PRegistryErrorCodes.AWE_WEBHOOK_UNSUPPORTED_ARTIFACT.value[0]}: "
                f"{event.artifact_type}"
            ),
        )

    async def _apply_stage_completed_event(self, event: AweWebhookEvent, session) -> None:
        """Non-terminal per-stage progress on a multi-stage policy (e.g. a
        hierarchical Kebele -> Woreda -> Zone -> Region approval chain) --
        unlike TERMINAL_EVENT_TYPES above, `stage_completed` fires once per
        stage as the request moves through a multi-stage policy, not just
        once at the very end. Only intake-form submissions are handled
        (change requests have no equivalent hook wired up yet). AweWebhookEvent
        carries no explicit per-stage outcome field, so a rejected stage is
        detected the same way engine.py itself distinguishes it: on a
        rejection the whole request's status is already flipped to
        "rejected" by the time this same stage_completed event is emitted
        (see awe/services/engine.py), so status=="rejected" here means this
        stage was a rejection, not an approval -- and request_rejected,
        handled separately by the terminal path above, already covers it.
        Delegates to the resolved domain service's post_approval_stage hook
        (no-op by default), same dispatch-by-register_mnemonic pattern
        save_intake_form_submission_with_session already uses -- silently a
        no-op for any register/domain-service that doesn't implement it.
        """
        if event.artifact_type != REGISTRY_INTAKE_FORM_ARTIFACT:
            return
        if event.status == "rejected":
            return
        if event.stage_order is None:
            return

        submission = await self._resolve_intake_form_submission(event, session)
        intake_service = G2PIntakeFormDataService.get_component()
        register_definition = await intake_service._get_register_definition(
            submission.register_id, session
        )

        import importlib

        domain_factory = getattr(
            importlib.import_module("openg2p_registry_extensions.register_domain.factory"),
            "G2PRegisterDomainFactory",
        ).get_component()
        domain_service = domain_factory.get_domain_service(register_definition.register_mnemonic)
        hook = getattr(domain_service, "post_approval_stage", None) if domain_service else None
        if hook is None:
            return
        await hook(submission, event.stage_order, "stage_completed", session)

    async def _apply_terminal_event_for_change_request(''',
    "g2p_awe_webhook_service.py: add _apply_stage_completed_event",
)

apply(
    f"{BASE}/services/g2p_awe_webhook_service.py",
    '''        submission = await self._resolve_intake_form_submission(event, session)
        intake_service = G2PIntakeFormDataService.get_component()

        if event.event_type == "request_approved":
            await intake_service.approve_submission_with_session(
                submission.submission_id,
                session,
                approved_by=event.actor,
            )
            return''',
    '''        submission = await self._resolve_intake_form_submission(event, session)
        intake_service = G2PIntakeFormDataService.get_component()

        if event.event_type == "request_approved":
            register_definition = await intake_service._get_register_definition(
                submission.register_id, session
            )
            import importlib

            domain_factory = getattr(
                importlib.import_module("openg2p_registry_extensions.register_domain.factory"),
                "G2PRegisterDomainFactory",
            ).get_component()
            domain_service = domain_factory.get_domain_service(register_definition.register_mnemonic)
            hook = getattr(domain_service, "post_approval_stage", None) if domain_service else None
            if hook is not None:
                # Final approval -- runs BEFORE approve_submission_with_session
                # below queues async ingest, so a field the hook sets here is
                # guaranteed to already be on the draft row by the time the
                # celery ingest worker copies it into the live register row
                # (which happens on its own schedule, not synchronously with
                # this webhook call).
                await hook(submission, event.stage_order, "request_approved", session)
            await intake_service.approve_submission_with_session(
                submission.submission_id,
                session,
                approved_by=event.actor,
            )
            return''',
    "g2p_awe_webhook_service.py: call post_approval_stage on final approval",
)

# ─── Fix 3: CSRF-exempt the livestock extension's approver-resolver endpoint
# (register_domain/controllers/g2p_approver_resolver_controller.py) — AWE's
# own "http" approver-rule caller (awe/services/resolver.py::_resolve_http)
# is a server-to-server POST with no CSRF cookie/header at all, same as the
# platform's own /awe/webhooks/decision (already in this list, protected by
# its own HMAC signature instead). This file lives in openg2p_registry_
# staff_api, a different installed package from every fix above, so it needs
# its own BASE.
# Only the staff-api image ships openg2p_registry_staff_api. This same script
# also runs in the partner-api image (see docker/partner-api/Dockerfile), where
# that package is absent; skip rather than fail so every image gets Fixes 1-2.
if os.path.exists(STAFF_API_MAIN):
    apply(
        STAFF_API_MAIN,
        '''    "/registrant-auth/callback",
    "/awe/webhooks/decision",
)''',
        '''    "/registrant-auth/callback",
    "/awe/webhooks/decision",
    "/livestock/approver-resolver",
)''',
        "openg2p_registry_staff_api/main.py: CSRF-exempt approver-resolver endpoint",
    )
else:
    print("SKIP: openg2p_registry_staff_api not installed in this image (partner-api) — Fix 3 not applicable")

# ─── Fix 7: new domain-service extension hook, pre_finalize, called once per
# section when staff click "Submit" on an intake form
# (finalize_intake_form_submission) — after the submission is marked FINAL but
# BEFORE its section payloads are built and handed to AWE as source_data, so
# whatever the hook writes onto the still-draft intake rows is what approvers
# see and what is later ingested. Added so the Farmer section's Farmer
# Registry enrichment runs once, on submit, instead of on every section save
# (post_intake_upsert) — see the livestock extension's
# g2p_register_domain_service_farmer.py for the override. Anchored on
# validate_intake_parent_link, which registry-platform 1.2 has (the 296 anchor,
# populate_link_internal_record_id_for_intake_form, is gone in 1.2).
apply(
    f"{BASE}/services/g2p_register_domain_service.py",
    '''    async def validate_intake_parent_link(''',
    '''    async def pre_finalize(self, rows: list, session: AsyncSession) -> None:
        """Optional extension hook: runs when an intake-form submission is
        finalized (staff "Submit"), once per section, with that section's
        intake-draft ORM rows -- after the submission is marked FINAL and
        BEFORE its section payloads are built for the AWE approval workflow,
        so anything set here is what approvers see and what is ingested.
        No-op by default."""
        pass

    async def validate_intake_parent_link(''',
    "g2p_register_domain_service.py: add pre_finalize hook",
)

apply(
    f"{BASE}/services/intake_form_data_service.py",
    '''        submission.draft_status = IntakeFormStatusEnum.FINAL.value
        submission.finalized_at = now
        submission.last_updated_at = now
        session.add(submission)
        await session.flush()
        section_payloads = await self._build_section_payloads(submission, session)''',
    '''        # Lock the submission row and read its status under the lock, so two
        # concurrent Submits (or a re-submit) cannot both run enrichment. Only the
        # DRAFT -> FINAL transition finalises and enriches; an already-FINAL
        # submission is returned unchanged (no row edits, no re-enrichment) so AWE
        # keeps reusing its original approval request. Reopening stays a separate
        # explicit action with its own lifecycle.
        _locked = (
            await session.execute(
                select(type(submission))
                .where(type(submission).submission_id == submission.submission_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalars().first()
        if _locked is not None and _locked.draft_status == IntakeFormStatusEnum.FINAL.value:
            return submission

        submission.draft_status = IntakeFormStatusEnum.FINAL.value
        submission.finalized_at = now
        submission.last_updated_at = now
        session.add(submission)
        await session.flush()

        module = importlib.import_module("openg2p_registry_extensions.register_domain.factory")
        domain_factory = getattr(module, "G2PRegisterDomainFactory").get_component()
        for section in await self._get_form_sections(submission.form_id, session):
            section_register_definition = await self._get_register_definition(section.section_register_id, session)
            domain_service = domain_factory.get_domain_service(section_register_definition.register_mnemonic)
            if not domain_service:
                continue
            _register_definition, intake_class, _register_class, _schema_class, _history_class = (
                await self._resolve_submission_models(section.section_register_id, session)
            )
            rows = (
                await session.execute(
                    select(intake_class).where(
                        *self._submission_section_filters(
                            intake_class,
                            submission.submission_id,
                            section.section_id,
                        )
                    )
                )
            ).scalars().all()
            if rows:
                await domain_service.pre_finalize(list(rows), session)
        await session.flush()

        section_payloads = await self._build_section_payloads(submission, session)''',
    "intake_form_data_service.py: call pre_finalize on submit",
)

print("ALL PATCHES APPLIED")
