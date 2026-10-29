"""Required fields through the registered intake service and real intake tables."""
import importlib
import os
import unittest
from datetime import datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from sqlalchemy import func, select

PACKAGE = os.environ.get("REGISTRY_EXTENSION_MODULE", "openg2p_registry_livestock_extension")
LIVESTOCK = "997676d3-7008-59f9-b23e-613ad79bbb08"
ANIMAL = "041a9f79-2142-548a-a15b-a4c76fc9f6f7"


def survey_schema():
    return {"section-title": "Survey Personnel", "panels": [{"widgets": [
        {"widget": "text", "widget-id": "surveyor_name", "widget-label": "Surveyor Name", "widget-required": True,
         "widget-data-path": LIVESTOCK + ".surveyor_name"},
        {"widget": "text", "widget-id": "supervisor_name", "widget-label": "Supervisor Name",
         "widget-data-path": LIVESTOCK + ".supervisor_name"},
    ]}]}


def animal_schema():
    def col(key, label, required):
        return {"widget": "select", "column-key": key, "widget-label": label, "widget-required": required}
    return {"section-title": "Livestock Details", "panels": [{"widgets": [{
        "widget": "dialog-table", "widget-id": "animals", "widget-label": "Livestock Details",
        "widget-data-columns": [col("species", "Species", True), col("breed", "Breed", True),
                                col("gender", "Sex", False)]}]}]}


@unittest.skipUnless(os.environ.get("FARMER_TEST_DATABASE_URL"), "Requires disposable PostgreSQL")
class RequiredIntakeNativeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.fixture = importlib.import_module("test_farmer_reference_native").NativeReferenceTests()
        await self.fixture.asyncSetUp()
        from openg2p_registry_core.models import (
            G2PIntakeFormDefinition, G2PIntakeFormUITab, G2PIntakeFormUITabSection,
            G2PRegisterDefinition, G2PRegisterSection)
        self.native = importlib.import_module("openg2p_registry_extensions.farmer_reference.native")
        self.service = self.native.G2PIntakeFormDataService.get_component()
        # The Animal domain rules (species codes, identifiers) have their own tests;
        # here only the required-field check is under test.
        services = importlib.import_module("openg2p_registry_extensions.register_domain.services")
        patcher = patch.object(services.G2PRegisterDomainServiceAnimal, "validate_domain_attributes", AsyncMock())
        patcher.start()
        self.addCleanup(patcher.stop)
        from sqlalchemy import text
        async with self.fixture.engine.begin() as connection:
            # The intake table of a row nobody has approved yet has no approval stamp.
            await connection.execute(text(
                "ALTER TABLE g2p_intake_form_animals ALTER COLUMN last_approved_at DROP NOT NULL"))
        async with self.fixture.sessions.begin() as session:
            session.add_all([
                G2PRegisterDefinition(register_id=LIVESTOCK, register_mnemonic="Livestock", register_subject="Synthetic",
                    register_purpose="REGISTER", register_rank=1, functional_id_generation_required=False),
                G2PRegisterDefinition(register_id=ANIMAL, register_mnemonic="Animal", register_subject="Synthetic",
                    register_purpose="REGISTER", register_rank=2, functional_id_generation_required=False,
                    master_register_id=LIVESTOCK)])
            await session.flush()
            session.add_all([
                G2PRegisterSection(register_id=LIVESTOCK, section_id="survey", section_register_id=LIVESTOCK,
                    section_mnemonic="survey", section_ui_schema=survey_schema(), no_of_verifications_required=0,
                    is_list=False),
                G2PRegisterSection(register_id=LIVESTOCK, section_id="animals", section_register_id=ANIMAL,
                    section_mnemonic="animals", section_ui_schema=animal_schema(), no_of_verifications_required=0,
                    is_list=True),
                G2PIntakeFormDefinition(form_id="form", register_id=LIVESTOCK, form_mnemonic="synthetic",
                    number_of_verifications=0, used_only_in_ingestion_pipeline=False),
                G2PIntakeFormUITab(tab_id="tab", form_id="form", tab_label="Synthetic", tab_order=1)])
            await session.flush()
            session.add_all([
                G2PIntakeFormUITabSection(tab_section_id="b1", tab_id="tab", section_id="survey", section_order=1),
                G2PIntakeFormUITabSection(tab_section_id="b2", tab_id="tab", section_id="animals", section_order=2)])

    async def asyncTearDown(self):
        await self.fixture.asyncTearDown()

    async def save(self, session, section_id, payload, submission_id=None):
        register = LIVESTOCK if section_id == "survey" else ANIMAL
        submission = await self.service.save_intake_form_submission_with_session(
            submission_id=submission_id, section_id=section_id, section_payload=payload,
            section_register_id=register, form_id="form", register_id=LIVESTOCK, created_by="tester",
            session=session)
        return submission.submission_id

    async def test_the_registered_service_carries_the_mixin(self):
        required = importlib.import_module("openg2p_registry_extensions.required_intake")
        self.assertIsInstance(self.service, required.RequiredFieldsMixin)

    async def test_save_refuses_an_empty_required_section_then_accepts_it_complete(self):
        from openg2p_registry_core.errors import G2PRegistryException
        async with self.fixture.sessions.begin() as session:
            with self.assertRaises(G2PRegistryException) as refused:
                await self.save(session, "survey", [{"supervisor_name": "Almaz"}])
            self.assertEqual(refused.exception.message, "Survey Personnel: fill in Surveyor Name")
            submission_id = await self.save(session, "survey", [{"surveyor_name": "Abebe", "supervisor_name": "Almaz"}])
            self.assertTrue(submission_id)

    async def test_stored_values_count_and_clearing_a_required_field_is_refused(self):
        from openg2p_registry_core.errors import G2PRegistryException
        async with self.fixture.sessions.begin() as session:
            submission_id = await self.save(session, "survey", [{"surveyor_name": "Abebe"}])
            # The staff UI sends only what changed.
            await self.save(session, "survey", [{"supervisor_name": "Almaz"}], submission_id)
            with self.assertRaises(G2PRegistryException) as refused:
                await self.save(session, "survey", [{"surveyor_name": ""}], submission_id)
            self.assertEqual(refused.exception.message, "Survey Personnel: fill in Surveyor Name")

    async def test_rows_are_checked_for_their_required_columns(self):
        from openg2p_registry_core.errors import G2PRegistryException
        async with self.fixture.sessions.begin() as session:
            submission_id = await self.save(session, "survey", [{"surveyor_name": "Abebe"}])
            with self.assertRaises(G2PRegistryException) as refused:
                await self.save(session, "animals", [{"species": "CATTLE", "breed": "BORAN"}, {"species": "GOAT"}],
                                submission_id)
            self.assertEqual(refused.exception.message, "Livestock Details, row 2: fill in Breed")
            await self.save(session, "animals", [{"species": "CATTLE", "breed": "BORAN"}], submission_id)

    async def _worker_finalize(self, session, submission_id):
        lookup = AsyncMock()
        with patch.object(importlib.import_module("openg2p_registry_extensions.farmer_reference.pending"),
                          "configured_lookup", return_value=type("L", (), {"lookup": lookup})()), \
             patch("openg2p_registry_extensions.farmer_reference.workflow.service_bearer",
                   AsyncMock(return_value="synthetic-worker-token")):
            try:
                return await self.service.finalize_submission_with_session(submission_id, session)
            finally:
                self.lookup = lookup

    async def test_finalize_refuses_an_incomplete_form_before_looking_up_the_farmer(self):
        from openg2p_registry_core.errors import G2PRegistryException
        from openg2p_registry_core.models import G2PIntakeFormSubmission
        async with self.fixture.sessions.begin() as session:
            # The animals were saved but the survey section was never filled (an ODK or
            # partner payload without it): it is still required at submit.
            submission_id = await self.save(session, "survey", [{"surveyor_name": "Abebe"}])
            root = (await session.execute(select(self.native.domain_models().G2PIntakeFormLivestock).where(
                self.native.domain_models().G2PIntakeFormLivestock.submission_id == submission_id))).scalar_one()
            root.surveyor_name = None
            await self.save(session, "animals", [{"species": "CATTLE", "breed": "BORAN"}], submission_id)
            with self.assertRaises(G2PRegistryException) as refused:
                await self._worker_finalize(session, submission_id)
            self.assertEqual(refused.exception.message, "Survey Personnel: fill in Surveyor Name")
            self.lookup.assert_not_awaited()
            submission = await session.get(G2PIntakeFormSubmission, submission_id)
            self.assertEqual(submission.draft_status, "DRAFT")

    async def test_finalize_refuses_an_incomplete_row_saved_earlier(self):
        from openg2p_registry_core.errors import G2PRegistryException
        async with self.fixture.sessions.begin() as session:
            submission_id = await self.save(session, "survey", [{"surveyor_name": "Abebe"}])
            animals = self.native.domain_models().G2PIntakeFormAnimal
            session.add(animals(internal_record_id=str(uuid4()), submission_id=submission_id, species="CATTLE",
                                created_by="tester", created_at=datetime.now(),
                                last_approved_at=datetime.now(), last_approved_by="tester"))
            await session.flush()
            with self.assertRaises(G2PRegistryException) as refused:
                await self._worker_finalize(session, submission_id)
            self.assertEqual(refused.exception.message, "Livestock Details, row 1: fill in Breed")
            self.assertEqual(await session.scalar(select(func.count()).select_from(
                importlib.import_module("openg2p_registry_extensions.farmer_reference.models").FarmerPendingLookup)), 0)
