"""The intake service refuses an incomplete section on save and an incomplete form on submit.

The mixin is exercised over a small in-memory stand-in for the platform intake
service, with the calls each channel makes: the staff UI (one section save per
Next, then a submit) and the ingestion worker used by ODK and partner pushes
(every section the payload carries is saved, then the form is finalized).
"""

import importlib
import os
import unittest
from types import SimpleNamespace

from openg2p_registry_core.errors import G2PRegistryException
from openg2p_registry_core.services.intake_form_data_service import G2PIntakeFormDataService

PACKAGE = os.environ.get("REGISTRY_EXTENSION_MODULE", "openg2p_registry_livestock_extension")
intake = importlib.import_module(PACKAGE + ".required_intake")

ROOT = "997676d3-7008-59f9-b23e-613ad79bbb08"
ANIMALS = "041a9f79-2142-548a-a15b-a4c76fc9f6f7"
EVENTS = "11111111-0000-4000-8000-000000000001"


def widget(field, label, *, required=False, actions=None, kind="text"):
    node = {"widget": kind, "widget-id": field, "widget-label": label, "widget-required": required,
            "widget-data-path": f"{ROOT}.{field}"}
    if actions:
        node["widget-data-options"] = {"actions": actions}
    return node


def column(field, label, *, required=False, actions=None, kind="text"):
    node = {"widget": kind, "column-key": field, "widget-label": label, "widget-required": required}
    if actions:
        node["widget-data-options"] = {"actions": actions}
    return node


def table(title, *columns, required=False):
    return {"section-title": title, "panels": [{"widgets": [{
        "widget": "dialog-table", "widget-id": "rows", "widget-label": title,
        "widget-required": required, "widget-data-columns": list(columns)}]}]}


def section(section_id, register_id, is_list, schema):
    return SimpleNamespace(section_id=section_id, section_register_id=register_id, is_list=is_list,
                           section_ui_schema=schema)


SECTIONS = [
    section("lookup", ROOT, False, {"section-title": "Farmer lookup", "panels": [{"widgets": [
        widget("farmer_id", "Farmer ID", required=True), widget("fayda_id", "Fayda ID", required=True)]}]}),
    section("location", ROOT, False, {"section-title": "Livestock Location", "panels": [{"widgets": [
        widget("kebele", "Kebele", required=True),
        widget("water_source", "Water Source", kind="select"),
        widget("water_other", "Other Water Source", actions=[
            {"action": "show", "condition": {"field": "water_source", "operator": "equals", "value": "OTHER"}},
            {"action": "require", "condition": {"field": "water_source", "operator": "equals", "value": "OTHER"}}]),
        widget("landmark", "Landmark")]}]}),
    section("animals", ANIMALS, True, table(
        "Livestock Details",
        column("species", "Species", required=True, kind="select"),
        column("breed", "Breed", required=True, kind="select"),
        column("weight", "Weight (kg)", kind="number"))),
    section("events", EVENTS, True, table(
        "Vital Event Details",
        column("event_type", "Event Type", required=True, kind="select"),
        column("disease_type", "Disease Type", kind="select", actions=[
            {"action": "show", "condition": {"field": "event_type", "operator": "equals", "value": "DISEASE"}},
            {"action": "require", "condition": {"field": "event_type", "operator": "equals", "value": "DISEASE"}}]))),
]
BY_ID = {s.section_id: s for s in SECTIONS}


class StandInPlatform:
    """Just enough of the platform intake service for the mixin."""

    _records_for_validation = staticmethod(G2PIntakeFormDataService._records_for_validation)

    def __init__(self):
        self.rows = {}  # (submission, register) -> {record id: row}
        self.finalized = []

    async def _get_section_or_error(self, section_id, session):
        return BY_ID[section_id]

    async def _get_submission_or_error(self, submission_id, session):
        return SimpleNamespace(submission_id=submission_id, form_id="form")

    async def _get_form_sections(self, form_id, session):
        return SECTIONS

    async def save_intake_form_submission_with_session(
        self, submission_id, section_id, section_payload, section_register_id,
        form_id, register_id, created_by, session, documents=None,
    ):
        store = self.rows.setdefault((submission_id, section_register_id), {})
        kept = {}
        for record in section_payload or []:
            if record.get("edit_action") == "DELETE":
                continue
            key = record.get("internal_record_id") or f"new-{len(kept)}"
            kept[key] = {**store.get(key, {}), **{k: v for k, v in record.items() if k != "edit_action"}}
        self.rows[(submission_id, section_register_id)] = kept
        return SimpleNamespace(submission_id=submission_id)

    async def finalize_submission_with_session(self, submission_id, session, finalized_by=None,
                                               bearer_token=None, requester_sub=None):
        self.finalized.append(submission_id)
        return SimpleNamespace(submission_id=submission_id, draft_status="FINAL")


class Service(intake.RequiredFieldsMixin, StandInPlatform):
    async def _required_messages(self):
        return {}

    async def _stored_records(self, submission_id, section_register_id, session):
        return dict(self.rows.get((submission_id, section_register_id), {}))

    async def _section_records(self, submission_id, section, session):
        return list(self.rows.get((submission_id, section.section_register_id), {}).values())


class RequiredIntakeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.service = Service()

    async def save(self, section_id, payload, submission_id="s1"):
        # The call the staff UI and the ingestion worker both make.
        return await self.service.save_intake_form_submission_with_session(
            submission_id=submission_id, section_id=section_id, section_payload=payload,
            section_register_id=BY_ID[section_id].section_register_id, form_id="form", register_id=ROOT,
            created_by="tester", session=None)

    async def refused(self, coroutine):
        with self.assertRaises(G2PRegistryException) as caught:
            await coroutine
        return caught.exception.message

    async def fill_form(self, submission_id="s1"):
        await self.save("lookup", [{"internal_record_id": "root", "farmer_id": "FR-000000000001",
                                    "fayda_fin": "001234567890"}], submission_id)
        await self.save("location", [{"internal_record_id": "root", "kebele": "Kebele 01"}], submission_id)
        await self.save("animals", [{"species": "CATTLE", "breed": "BORAN"}], submission_id)

    # ----- save

    async def test_save_refuses_an_empty_required_section(self):
        message = await self.refused(self.save("location", [{"internal_record_id": "root", "landmark": "Church"}]))
        self.assertEqual(message, "Livestock Location: fill in Kebele")
        self.assertEqual(self.service.rows, {})

    async def test_save_passes_a_complete_section(self):
        await self.save("location", [{"internal_record_id": "root", "kebele": "Kebele 01"}])
        self.assertEqual(self.service.rows[("s1", ROOT)]["root"]["kebele"], "Kebele 01")

    async def test_stored_values_count_because_the_ui_omits_untouched_fields(self):
        await self.save("location", [{"internal_record_id": "root", "kebele": "Kebele 01"}])
        await self.save("location", [{"internal_record_id": "root", "landmark": "Church"}])
        self.assertEqual(self.service.rows[("s1", ROOT)]["root"]["kebele"], "Kebele 01")

    async def test_clearing_a_required_field_is_refused(self):
        await self.save("location", [{"internal_record_id": "root", "kebele": "Kebele 01"}])
        message = await self.refused(self.save("location", [{"internal_record_id": "root", "kebele": ""}]))
        self.assertEqual(message, "Livestock Location: fill in Kebele")
        self.assertEqual(self.service.rows[("s1", ROOT)]["root"]["kebele"], "Kebele 01")

    async def test_a_hidden_field_is_not_required_and_a_shown_one_is(self):
        await self.save("location", [{"internal_record_id": "root", "kebele": "K", "water_source": "RIVER"}])
        message = await self.refused(
            self.save("location", [{"internal_record_id": "root", "kebele": "K", "water_source": "OTHER"}]))
        self.assertEqual(message, "Livestock Location: fill in Other Water Source")

    async def test_the_require_rule_is_enforced_on_save(self):
        message = await self.refused(self.save("events", [{"event_type": "DISEASE"}]))
        self.assertEqual(message, "Vital Event Details, row 1: fill in Disease Type")
        await self.save("events", [{"event_type": "BIRTH"}])

    async def test_row_columns_are_checked_and_every_row_is_named(self):
        message = await self.refused(self.save("animals", [
            {"species": "CATTLE", "breed": "BORAN"}, {"species": "GOAT"}, {"weight": 3}]))
        self.assertEqual(message, "Livestock Details, row 2: fill in Breed; "
                                  "Livestock Details, row 3: fill in Species, Breed")

    async def test_a_list_section_with_no_rows_passes_when_its_table_is_optional(self):
        await self.save("animals", [])

    async def test_a_required_table_with_no_rows_is_refused(self):
        original = BY_ID["animals"].section_ui_schema
        BY_ID["animals"].section_ui_schema = table("Livestock Details", column("species", "Species"), required=True)
        try:
            message = await self.refused(self.save("animals", []))
        finally:
            BY_ID["animals"].section_ui_schema = original
        self.assertEqual(message, "Livestock Details: add at least one row")

    async def test_deleted_rows_are_not_checked(self):
        await self.save("animals", [{"species": "CATTLE", "breed": "BORAN"},
                                    {"internal_record_id": "gone", "edit_action": "DELETE"}])

    async def test_the_farmer_lookup_section_keeps_its_own_validation(self):
        await self.save("lookup", [{"internal_record_id": "root", "landmark": "x"}])

    # ----- submit

    async def test_web_submit_refuses_an_incomplete_form_including_a_section_never_opened(self):
        # The person filled the lookup and the location and pressed Submit; the animals
        # section was never opened, so its (optional) table is fine, but a row saved
        # earlier with a gap is not.
        await self.save("location", [{"internal_record_id": "root", "kebele": "Kebele 01"}])
        self.service.rows[("s1", ANIMALS)] = {"a": {"species": "CATTLE"}}
        message = await self.refused(self.service.finalize_submission_with_session("s1", None, "tester"))
        self.assertEqual(message, "Livestock Details, row 1: fill in Breed")
        self.assertEqual(self.service.finalized, [])

    async def test_submit_checks_a_required_section_that_was_never_saved(self):
        message = await self.refused(self.service.finalize_submission_with_session("s1", None))
        self.assertEqual(message, "Livestock Location: fill in Kebele")

    async def test_submit_passes_a_complete_form(self):
        await self.fill_form()
        result = await self.service.finalize_submission_with_session("s1", None, "tester", bearer_token="t")
        self.assertEqual(result.draft_status, "FINAL")
        self.assertEqual(self.service.finalized, ["s1"])

    async def test_odk_and_partner_ingestion_is_refused_the_same_way(self):
        # The worker saves the sections the payload carries, then finalizes with no bearer.
        await self.save("lookup", [{"internal_record_id": "root", "farmer_id": "FR-000000000001"}], "odk")
        await self.save("animals", [{"species": "CATTLE", "breed": "BORAN"}], "odk")
        message = await self.refused(self.service.finalize_submission_with_session("odk", None))
        self.assertEqual(message, "Livestock Location: fill in Kebele")
        self.assertEqual(self.service.finalized, [])

    async def test_an_incomplete_ingested_section_is_refused_on_save(self):
        message = await self.refused(self.save("animals", [{"species": "CATTLE"}], "partner"))
        self.assertEqual(message, "Livestock Details, row 1: fill in Breed")

    async def test_odk_and_partner_ingestion_passes_when_complete(self):
        await self.fill_form("odk")
        await self.service.finalize_submission_with_session("odk", None)
        self.assertEqual(self.service.finalized, ["odk"])

    async def test_a_caller_that_already_checked_is_not_checked_twice(self):
        calls = []
        original = self.service._required_on_finalize

        async def counting(*args):
            calls.append(args)
            return await original(*args)

        self.service._required_on_finalize = counting
        await self.fill_form()
        await self.service.ensure_complete_on_finalize("s1", None)
        await self.service.finalize_submission_with_session("s1", None, required_checked=True)
        self.assertEqual(len(calls), 1)

    async def test_the_refusal_is_a_validation_error_with_one_readable_sentence(self):
        with self.assertRaises(G2PRegistryException) as caught:
            await self.service.finalize_submission_with_session("empty", None)
        self.assertEqual(caught.exception.code, "REQ-VAL-001")
        self.assertNotIn("_", caught.exception.message)


class IntakeServiceOrderTests(unittest.TestCase):
    def test_the_mixin_follows_the_fayda_view_and_direct_approval_stays_before_the_platform_class(self):
        from importlib import import_module
        native = import_module(PACKAGE + ".farmer_reference.native")
        direct = import_module(PACKAGE + ".direct_approval")
        view = import_module(PACKAGE + ".fayda_id_view")
        mro = native.ReferenceIntakeService.__mro__
        self.assertIs(mro[1], view.FaydaIdMixin)
        self.assertIs(mro[2], intake.RequiredFieldsMixin)
        self.assertLess(mro.index(direct.DirectApprovalClosed), mro.index(native.G2PIntakeFormDataService))

    def test_no_class_redefines_a_direct_approval_method(self):
        from importlib import import_module
        native = import_module(PACKAGE + ".farmer_reference.native")
        direct = import_module(PACKAGE + ".direct_approval")
        for cls in (intake.RequiredFieldsMixin, native.ReferenceIntakeService, native.ReferenceChangeRequestService):
            for name in ("approve_submission", "approve_change_request"):
                if cls is native.ReferenceChangeRequestService and name == "approve_submission":
                    continue
                self.assertNotIn(name, vars(cls), f"{cls.__name__} must not redefine {name}")
        self.assertIn("approve_submission", vars(direct.DirectApprovalClosed))
