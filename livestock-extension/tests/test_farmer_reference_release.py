"""Held approved intakes are released by their readable text and by the older codes."""
import importlib
import os
import unittest
from datetime import datetime
from uuid import uuid4

PACKAGE = os.environ.get("REGISTRY_EXTENSION_MODULE", "openg2p_registry_livestock_extension")
LEGACY_PENDING = "FARMER_REFERENCE_DEPENDENCY_PENDING"


@unittest.skipUnless(os.environ.get("FARMER_TEST_DATABASE_URL"), "Requires disposable PostgreSQL")
class ReleaseHeldIntakeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.fixture = importlib.import_module("test_farmer_reference_native").NativeReferenceTests()
        await self.fixture.asyncSetUp()
        self.native = importlib.import_module("openg2p_registry_extensions.farmer_reference.native")
        self.models = importlib.import_module("openg2p_registry_extensions.farmer_reference.models")
        self.messages = importlib.import_module("openg2p_registry_extensions.farmer_reference.messages")

    async def asyncTearDown(self):
        await self.fixture.asyncTearDown()

    async def held_intake(self, session, held_text, reference_state):
        from openg2p_registry_core.models import G2PIntakeFormSubmission, G2PRegisterDefinition
        domain_id = "997676d3-7008-59f9-b23e-613ad79bbb08"
        if await session.get(G2PRegisterDefinition, domain_id) is None:
            session.add(G2PRegisterDefinition(register_id=domain_id, register_mnemonic="Livestock",
                register_subject="Synthetic", register_purpose="REGISTER", register_rank=1,
                functional_id_generation_required=False))
        suffix = uuid4().hex
        submission_id = str(uuid4())
        submission = G2PIntakeFormSubmission(submission_id=submission_id, form_id="synthetic-form",
            register_id=domain_id, draft_status="FINAL", approval_status="APPROVED", created_by="synthetic",
            first_created_at=datetime.now(), last_updated_at=datetime.now(), submission_source="PARTNER",
            register_ingest_process_status="NOT_APPLICABLE", number_of_verifications_required=0,
            number_of_verifications_done=0, register_ingest_process_last_error_code=held_text)
        root = self.native.domain_models().G2PIntakeFormLivestock(internal_record_id=str(uuid4()),
            submission_id=submission_id, farmer_id="FR-000000000001", fayda_fin="001234567890",
            farmer_reference_status=held_text, created_by="synthetic", created_at=datetime.now(),
            last_approved_at=datetime.now(), last_approved_by="synthetic")
        reference = self.models.FarmerReference(reference_id="ref-" + suffix, source_system="source-" + suffix,
            source_record_id="person-" + suffix, farmer_id="FR-000000000001", uid="0000000000000001",
            local_farmer_id=str(uuid4()), state=reference_state)
        session.add_all([submission, root, reference])
        await session.flush()
        session.add(self.models.FarmerSubmissionDependency(submission_id=submission_id,
            reference_id=reference.reference_id))
        await session.flush()
        return submission, root

    async def test_rows_held_with_the_old_code_are_released_when_the_farmer_is_approved(self):
        async with self.fixture.sessions.begin() as session:
            submission, root = await self.held_intake(session, LEGACY_PENDING, "APPROVED")
            self.assertEqual(await self.native.release_waiting_domains(session), 1)
            self.assertEqual(submission.register_ingest_process_status, "PENDING")
            self.assertIsNone(submission.register_ingest_process_last_error_code)
            self.assertEqual(root.farmer_reference_status, self.messages.FARMER_REFERENCE_LINKED)

    async def test_rows_held_with_the_readable_text_are_released_too(self):
        async with self.fixture.sessions.begin() as session:
            submission, root = await self.held_intake(session, self.messages.WAITING_FOR_FARMER_APPROVAL, "APPROVED")
            self.assertEqual(await self.native.release_waiting_domains(session), 1)
            self.assertEqual(submission.register_ingest_process_status, "PENDING")
            self.assertEqual(root.farmer_reference_status, self.messages.FARMER_REFERENCE_LINKED)

    async def test_a_rejected_farmer_leaves_the_readable_rejection_on_the_intake(self):
        async with self.fixture.sessions.begin() as session:
            submission, root = await self.held_intake(session, LEGACY_PENDING, "REJECTED")
            self.assertEqual(await self.native.release_waiting_domains(session), 1)
            self.assertEqual(submission.register_ingest_process_status, "NOT_APPLICABLE")
            self.assertEqual(submission.register_ingest_process_last_error_code, self.messages.FARMER_APPROVAL_REJECTED)
            self.assertEqual(root.farmer_reference_status, self.messages.FARMER_APPROVAL_REJECTED)
            self.assertNotIn("FARMER_REFERENCE_", submission.register_ingest_process_last_error_code)

    async def test_a_row_that_is_not_waiting_is_left_alone(self):
        async with self.fixture.sessions.begin() as session:
            submission, _ = await self.held_intake(session, self.messages.FARMER_APPROVAL_REJECTED, "APPROVED")
            self.assertEqual(await self.native.release_waiting_domains(session), 0)
            self.assertEqual(submission.register_ingest_process_status, "NOT_APPLICABLE")
