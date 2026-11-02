"""Run the domain services' post_intake_upsert after every intake section save.

registry-platform 1.2 validates a section save through
validate_domain_attributes only, and hands it the raw payload rows: no
submission, no application reference. The checks that need to know which
submission is being saved live in the domain services' post_intake_upsert,
which the platform no longer calls:

- the same new ear tag, identifier, mortality or health / vaccination /
  breeding event drafted in another submission;
- an event on an animal that is not part of this submission (another
  holding's animal, or one drafted only in another draft);
- a BIRTH row's offspring ear tags, reserved as soon as the section is saved;
- the Livestock row's admin area names and farmer identity.

This mixin calls it right after the platform has upserted the section's rows,
in the same session, with the rows of that register this save added or
changed. A refusal raised there rolls the whole section save back, because the platform
commits only after this method returns. Web, ODK and partner ingestion all
save sections through this service, so every channel gets the same checks.

Put it in the intake service's bases, before the platform service.
"""

from openg2p_registry_core.interfaces import G2PRegisterDomainFactory

from .register_domain.services.domain_validation_utils import ingest_session


class IntakeUpsertHook:
    async def save_intake_form_submission_with_session(
        self, submission_id, section_id, section_payload, section_register_id,
        form_id, register_id, created_by, session, documents=None,
    ):
        # The checks read through this save's own session, so they see rows it
        # has flushed but not committed (the ingest worker commits once, after
        # every section; a separate connection would not see this submission's
        # animals).
        token = ingest_session.set(session)
        try:
            existing = await self._existing_row_ids(submission_id, section_register_id, session)
            submission = await super().save_intake_form_submission_with_session(
                submission_id, section_id, section_payload, section_register_id,
                form_id, register_id, created_by, session, documents=documents)
            await self._run_post_intake_upsert(
                submission, section_register_id, session, saved_row_ids(section_payload), existing)
            return submission
        finally:
            ingest_session.reset(token)

    async def _existing_row_ids(self, submission_id, section_register_id, session) -> set:
        """internal_record_id of the submission's rows of this register before the save."""
        if not submission_id:
            return set()
        intake_class = await self._resolve_intake_form_class(section_register_id, session)
        return set(await self._get_intake_rows(intake_class, submission_id, session))

    async def _run_post_intake_upsert(
        self, submission, section_register_id, session, saved_ids=None, existing=None
    ) -> None:
        definition = await self._get_register_definition(section_register_id, session)
        factory = G2PRegisterDomainFactory.get_component() or G2PRegisterDomainFactory()
        domain_service = factory.get_domain_service(definition.register_mnemonic)
        hook = getattr(domain_service, "post_intake_upsert", None)
        if hook is None:
            return
        intake_class = await self._resolve_intake_form_class(section_register_id, session)
        rows = list(await self._get_intake_rows_list(intake_class, submission.submission_id, session))
        if saved_ids is not None:
            # Only the rows this save sent back or inserted: every check opens
            # a query per row, so re-checking the whole herd on each Next would
            # cost two queries per animal.
            existing = existing or set()
            rows = [row for row in rows
                    if getattr(row, "internal_record_id", None) in saved_ids
                    or getattr(row, "internal_record_id", None) not in existing]
        if not rows:
            return
        await hook(rows, session)
        await session.flush()


def saved_row_ids(section_payload) -> set:
    """internal_record_id of the existing rows a section save sends back (deleted ones excluded)."""
    return {
        record["internal_record_id"]
        for record in section_payload or []
        if isinstance(record, dict) and record.get("internal_record_id") and record.get("edit_action") != "DELETE"
    }
