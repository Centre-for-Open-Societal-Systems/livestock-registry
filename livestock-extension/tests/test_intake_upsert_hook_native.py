"""The post-save domain checks through the registered intake service and real intake tables."""
import importlib
import os
import unittest
from unittest.mock import AsyncMock, patch

from sqlalchemy import func, select

PACKAGE = os.environ.get("REGISTRY_EXTENSION_MODULE", "openg2p_registry_livestock_extension")
LIVESTOCK = "997676d3-7008-59f9-b23e-613ad79bbb08"
ANIMAL = "041a9f79-2142-548a-a15b-a4c76fc9f6f7"
HEALTH = "a40e4a02-1b82-5b31-89df-71624bd96545"
REGISTERS = {"survey": LIVESTOCK, "animals": ANIMAL, "health": HEALTH}


def text_widget(field):
    return {"widget": "text", "widget-id": field, "widget-label": field, "widget-data-path": LIVESTOCK + "." + field}


def table(title, *keys):
    return {"section-title": title, "panels": [{"widgets": [{
        "widget": "dialog-table", "widget-id": title, "widget-label": title,
        "widget-data-columns": [{"widget": "text", "column-key": key, "widget-label": key} for key in keys]}]}]}


def animal(tag):
    return {"ear_tag_id": tag, "species": "CATTLE", "breed": "BREED_LOCAL", "edit_action": "ADD"}


def injury(tag):
    return {"ear_tag_id": tag, "event_type": "INJURY", "date_onset": "2026-10-12", "date_resolution": "2026-10-14",
            "edit_action": "ADD"}


@unittest.skipUnless(os.environ.get("FARMER_TEST_DATABASE_URL"), "Requires disposable PostgreSQL")
class IntakeUpsertHookNativeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.fixture = importlib.import_module("test_farmer_reference_native").NativeReferenceTests()
        await self.fixture.asyncSetUp()
        from openg2p_fastapi_common.context import dbengine
        from openg2p_registry_core.models import (
            G2PIntakeFormDefinition, G2PIntakeFormUITab, G2PIntakeFormUITabSection,
            G2PRegisterDefinition, G2PRegisterSection)
        from sqlalchemy import text
        native = importlib.import_module("openg2p_registry_extensions.farmer_reference.native")
        self.service = native.G2PIntakeFormDataService.get_component()
        # The checks that do not need the submission (species codes, formats)
        # have their own tests; here only the post-save checks are under test.
        services = importlib.import_module("openg2p_registry_extensions.register_domain.services")
        for name in ("G2PRegisterDomainServiceAnimal", "G2PRegisterDomainServiceHealthEvent",
                     "G2PRegisterDomainServiceLivestock"):
            patcher = patch.object(getattr(services, name), "validate_domain_attributes", AsyncMock())
            patcher.start()
            self.addCleanup(patcher.stop)
        # Checks that look across drafts open their own connection on the app engine.
        previous_engine = dbengine.get()
        dbengine.set(self.fixture.engine)
        self.addCleanup(dbengine.set, previous_engine)
        async with self.fixture.engine.begin() as connection:
            for intake_table in ("g2p_intake_form_livestocks", "g2p_intake_form_animals", "g2p_intake_form_health_events"):
                await connection.execute(text(f"ALTER TABLE {intake_table} ALTER COLUMN last_approved_at DROP NOT NULL"))
        async with self.fixture.sessions.begin() as session:
            session.add(G2PRegisterDefinition(register_id=LIVESTOCK, register_mnemonic="Livestock",
                register_subject="Synthetic", register_purpose="REGISTER", register_rank=1,
                functional_id_generation_required=False))
            await session.flush()
            for register_id, mnemonic, rank in ((ANIMAL, "Animal", 2), (HEALTH, "HealthEvent", 3)):
                session.add(G2PRegisterDefinition(register_id=register_id, register_mnemonic=mnemonic,
                    register_subject="Synthetic", register_purpose="REGISTER", register_rank=rank,
                    functional_id_generation_required=False, master_register_id=LIVESTOCK))
            await session.flush()
            session.add_all([
                G2PRegisterSection(register_id=LIVESTOCK, section_id="survey", section_register_id=LIVESTOCK,
                    section_mnemonic="survey", no_of_verifications_required=0, is_list=False,
                    section_ui_schema={"section-title": "Survey", "panels": [{"widgets": [text_widget("surveyor_name")]}]}),
                G2PRegisterSection(register_id=LIVESTOCK, section_id="animals", section_register_id=ANIMAL,
                    section_mnemonic="animals", no_of_verifications_required=0, is_list=True,
                    section_ui_schema=table("Livestock details", "ear_tag_id", "species", "breed")),
                G2PRegisterSection(register_id=LIVESTOCK, section_id="health", section_register_id=HEALTH,
                    section_mnemonic="health", no_of_verifications_required=0, is_list=True,
                    section_ui_schema=table("Health events", "ear_tag_id", "event_type", "date_onset", "date_resolution")),
                G2PIntakeFormDefinition(form_id="form", register_id=LIVESTOCK, form_mnemonic="synthetic",
                    number_of_verifications=0, used_only_in_ingestion_pipeline=False),
                G2PIntakeFormUITab(tab_id="tab", form_id="form", tab_label="Synthetic", tab_order=1)])
            await session.flush()
            session.add_all([
                G2PIntakeFormUITabSection(tab_section_id=f"b{order}", tab_id="tab", section_id=section, section_order=order)
                for order, section in enumerate(("survey", "animals", "health"), 1)])

    async def asyncTearDown(self):
        await self.fixture.asyncTearDown()

    async def save(self, session, section_id, payload, submission_id=None):
        submission = await self.service.save_intake_form_submission_with_session(
            submission_id=submission_id, section_id=section_id, section_payload=payload,
            section_register_id=REGISTERS[section_id], form_id="form", register_id=LIVESTOCK,
            created_by="tester", session=session)
        return submission.submission_id

    async def draft_with_animal(self, tag):
        async with self.fixture.sessions.begin() as session:
            submission_id = await self.save(session, "survey", [{"surveyor_name": "Abebe"}])
            await self.save(session, "animals", [animal(tag)], submission_id)
        return submission_id

    async def count_health_events(self):
        models = importlib.import_module("openg2p_registry_extensions.register_domain.models")
        async with self.fixture.sessions() as session:
            return await session.scalar(select(func.count()).select_from(models.G2PIntakeFormHealthEvent))

    async def test_a_worker_transaction_sees_its_own_unsaved_animal(self):
        # The ingest worker saves every section in one transaction and commits
        # after finalize; the event's animal exists only in that transaction.
        async with self.fixture.sessions.begin() as session:
            submission_id = await self.save(session, "survey", [{"surveyor_name": "Abebe"}])
            await self.save(session, "animals", [animal("ET0000000101")], submission_id)
            await self.save(session, "health", [injury("ET0000000101")], submission_id)
        self.assertEqual(await self.count_health_events(), 1)

    async def test_an_event_on_another_drafts_animal_is_refused_and_rolled_back(self):
        from openg2p_registry_core.errors import G2PRegistryException
        await self.draft_with_animal("ET0000000201")
        other = await self.draft_with_animal("ET0000000202")
        with self.assertRaises(G2PRegistryException) as refused:
            async with self.fixture.sessions.begin() as session:
                await self.save(session, "health", [injury("ET0000000201")], other)
        self.assertIn("'ET0000000201' is not an animal of this submission", refused.exception.message)
        self.assertEqual(await self.count_health_events(), 0)

    async def test_a_new_ear_tag_drafted_elsewhere_is_refused(self):
        from openg2p_registry_core.errors import G2PRegistryException
        await self.draft_with_animal("ET0000000301")
        other = await self.draft_with_animal("ET0000000302")
        with self.assertRaises(G2PRegistryException) as refused:
            async with self.fixture.sessions.begin() as session:
                await self.save(session, "animals", [animal("ET0000000301")], other)
        self.assertIn("ET0000000301", refused.exception.message)
        self.assertIn("another intake form", refused.exception.message)
