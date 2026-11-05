"""The Farmer lookup box shows the saved Fayda ID and a re-save keeps it."""
import importlib
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

PACKAGE = "openg2p_registry_livestock_extension"
native = importlib.import_module(PACKAGE + ".farmer_reference.native")
view = importlib.import_module(PACKAGE + ".fayda_id_view")
rules = importlib.import_module(PACKAGE + ".register_domain.services.field_rules")

FIN = "808745702436"
FAN = "1234567890123456"
OTHER_FIN = "111122223333"
Platform = native.G2PIntakeFormDataService


def item(*records):
    return SimpleNamespace(records=list(records))


class Row:
    fayda_fin = fayda_fan_id = None

    def __init__(self, fin=None, fan=None):
        self.fayda_fin, self.fayda_fan_id = fin, fan


class ReadTests(unittest.IsolatedAsyncioTestCase):
    def test_service_uses_the_mixin_first(self):
        self.assertIs(native.ReferenceIntakeService.__mro__[1], view.FaydaIdMixin)

    async def read(self, method, *records):
        service = object.__new__(native.ReferenceIntakeService)
        with patch.object(Platform, method, AsyncMock(return_value=[item(*records)])):
            if method == "get_tab_records":
                return (await service.get_tab_records("s1", "t1"))[0].records
            return (await service._build_section_payloads(SimpleNamespace(), None))[0].records

    async def test_saved_fin_is_returned_as_fayda_id(self):
        for method in ("_build_section_payloads", "get_tab_records"):
            records = await self.read(method, {"farmer_id": "FR-906129387150", "fayda_fin": FIN, "fayda_fan_id": None})
            self.assertEqual(records[0]["fayda_id"], FIN)
            self.assertEqual(records[0]["fayda_fin"], FIN)

    async def test_saved_fan_is_returned_as_fayda_id(self):
        records = await self.read("_build_section_payloads", {"fayda_fin": None, "fayda_fan_id": FAN})
        self.assertEqual(records[0]["fayda_id"], FAN)

    async def test_nothing_saved_gives_an_empty_box_and_other_sections_are_untouched(self):
        records = await self.read("get_tab_records", {"fayda_fin": None, "fayda_fan_id": " "}, {"crop_year": 2026})
        self.assertIsNone(records[0]["fayda_id"])
        self.assertNotIn("fayda_id", records[1])


class SaveTests(unittest.IsolatedAsyncioTestCase):
    async def save(self, payload, stored_rows):
        service = object.__new__(native.ReferenceIntakeService)
        service._resolve_intake_form_class = AsyncMock(return_value=Row)
        service._get_intake_rows = AsyncMock(return_value=stored_rows)
        # The required-field check and the post-save domain hook have their own tests;
        # here only the Fayda ID handling is under test.
        service._required_on_save = AsyncMock(return_value=[])
        service._run_post_intake_upsert = AsyncMock()
        platform = AsyncMock(return_value="submission")
        with patch.object(Platform, "save_intake_form_submission_with_session", platform):
            await service.save_intake_form_submission_with_session(
                "s1", "sec", payload, "reg", "form", "reg", "user", None)
        sent = platform.call_args.args[2]
        self.assertIs(sent, payload)
        return sent

    async def test_blank_box_keeps_a_stored_fin_or_fan(self):
        for row in (Row(fin=FIN), Row(fan=FAN)):
            payload = [{"internal_record_id": "r1", "farmer_id": "FR-906129387150", "fayda_id": ""}]
            sent = await self.save(payload, {"r1": row})
            self.assertNotIn("fayda_id", sent[0])
            self.assertEqual(rules.clean_records(sent), [])
            self.assertNotIn("fayda_fin", sent[0])
            self.assertNotIn("fayda_fan_id", sent[0])

    async def test_blank_box_next_to_the_stored_columns_is_not_refused(self):
        payload = [{"internal_record_id": "r1", "farmer_id": "FR-906129387150", "fayda_fin": FIN,
                    "fayda_fan_id": None, "fayda_id": None}]
        sent = await self.save(payload, {})
        self.assertEqual(rules.clean_records(sent), [])
        self.assertEqual(sent[0]["fayda_fin"], FIN)

    async def test_unchanged_value_posted_back_keeps_the_stored_value(self):
        payload = [{"internal_record_id": "r1", "farmer_id": "FR-906129387150", "fayda_id": FIN}]
        sent = await self.save(payload, {"r1": Row(fin=FIN)})
        self.assertEqual(rules.clean_records(sent), [])
        self.assertEqual((sent[0]["fayda_fin"], sent[0]["fayda_fan_id"]), (FIN, None))

    async def test_changed_value_still_updates(self):
        payload = [{"internal_record_id": "r1", "farmer_id": "FR-906129387150", "fayda_id": OTHER_FIN}]
        sent = await self.save(payload, {"r1": Row(fin=FIN)})
        self.assertEqual(rules.clean_records(sent), [])
        self.assertEqual((sent[0]["fayda_fin"], sent[0]["fayda_fan_id"]), (OTHER_FIN, None))
        payload = [{"internal_record_id": "r1", "fayda_id": FAN}]
        sent = await self.save(payload, {"r1": Row(fin=FIN)})
        self.assertEqual(rules.clean_records(sent), [])
        self.assertEqual((sent[0]["fayda_fin"], sent[0]["fayda_fan_id"]), (None, FAN))

    async def test_blank_box_with_nothing_stored_is_still_refused(self):
        for rows in ({}, {"r1": Row()}):
            payload = [{"internal_record_id": "r1", "farmer_id": "FR-906129387150", "fayda_id": ""}]
            sent = await self.save(payload, rows)
            self.assertIn("fayda_id", sent[0])
            self.assertTrue(rules.clean_records(sent))

    async def test_a_new_record_does_not_borrow_another_records_value(self):
        payload = [{"internal_record_id": "new", "fayda_id": ""}]
        sent = await self.save(payload, {"r1": Row(fin=FIN)})
        self.assertIn("fayda_id", sent[0])

    async def test_a_deleted_record_is_left_alone(self):
        payload = [{"internal_record_id": "r1", "edit_action": "DELETE", "fayda_id": ""}]
        sent = await self.save(payload, {"r1": Row(fin=FIN)})
        self.assertIn("fayda_id", sent[0])
