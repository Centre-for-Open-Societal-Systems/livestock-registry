"""The seed removes the old validation keys, rule ids and panel id from a database seeded earlier."""
import importlib
import json
import os
import re
import sys
import unittest
from pathlib import Path
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

PACKAGE = os.environ.get("REGISTRY_EXTENSION_MODULE", "openg2p_registry_livestock_extension")
sys.modules.setdefault("openg2p_registry_extensions", importlib.import_module(PACKAGE))
META = Path(importlib.import_module(PACKAGE).__file__).parent / "meta_data"
CLEANUP = (META / "zz-oan/95_validation_keys.sql").read_text(encoding="utf-8")
LOCATION = (META / "register-metadata/zzzz_location_widgets.sql").read_text(encoding="utf-8")
OLD_KEY = re.compile(r"coss_(input_|field_|code_choice|location_widgets)")


def seeded_before_the_rename():
    return {"panels": [{"panel-id": "coss_location_widgets", "widgets": [
        {"widget-id": "first_name", "widget-data-validation": {"pattern": "^x$", "patternMessage": "coss_input_first_name"},
         "widget-data-options": {"minDateMessage": "coss_input_date_of_birth_min"}}]}]}


@unittest.skipUnless(os.environ.get("FARMER_TEST_DATABASE_URL"), "Requires owned disposable PostgreSQL")
class ValidationKeyCleanupTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.url = os.environ["FARMER_TEST_DATABASE_URL"]
        self.name = "oan_seed_test_" + uuid4().hex
        admin = create_async_engine(self.url, isolation_level="AUTOCOMMIT")
        async with admin.connect() as conn:
            await conn.execute(text('CREATE DATABASE "' + self.name + '"'))
        await admin.dispose()
        self.engine = create_async_engine(make_url(self.url).set(database=self.name))
        async with self.engine.begin() as conn:
            await conn.execute(text("CREATE TABLE registry_languages (language_id text PRIMARY KEY, domain_translation json)"))
            await conn.execute(text("CREATE TABLE g2p_register_sections (section_id text PRIMARY KEY, section_ui_schema jsonb)"))
            await conn.execute(text("INSERT INTO registry_languages VALUES ('en', CAST(:t AS json)), ('am', CAST(:a AS json)), ('none', NULL)"), {
                "t": json.dumps({"coss_input_first_name": "old text", "validation_first_name": "new text",
                                 "coss_field_row_label": "{label} (row {row})", "coss_code_choice": "choose one",
                                 "unrelated": "kept"}),
                "a": json.dumps({"coss_input_first_name": "amharic text"})})
            await conn.execute(text("INSERT INTO g2p_register_sections VALUES ('livestock_livestock_location_section_03', CAST(:s AS jsonb))"),
                               {"s": json.dumps(seeded_before_the_rename())})

    async def asyncTearDown(self):
        await self.engine.dispose()
        assert re.fullmatch("oan_seed_test_[0-9a-f]{32}", self.name)
        admin = create_async_engine(self.url, isolation_level="AUTOCOMMIT")
        async with admin.connect() as conn:
            await conn.execute(text('DROP DATABASE "' + self.name + '" WITH (FORCE)'))
        await admin.dispose()

    async def run_script(self, script):
        async with self.engine.connect() as conn:
            raw = await conn.get_raw_connection()
            await raw.driver_connection.execute(script)

    async def state(self):
        async with self.engine.connect() as conn:
            languages = {row[0]: row[1] for row in await conn.execute(text("SELECT language_id, domain_translation FROM registry_languages"))}
            section = (await conn.execute(text("SELECT section_ui_schema FROM g2p_register_sections"))).scalar_one()
        return languages, section

    async def test_old_keys_move_to_the_new_names_and_none_is_left(self):
        await self.run_script(CLEANUP)
        languages, section = await self.state()
        self.assertEqual(languages["en"], {"validation_first_name": "new text", "validation_rule_row_label": "{label} (row {row})",
                                           "validation_code_choice": "choose one", "unrelated": "kept"})
        self.assertEqual(languages["am"], {"validation_first_name": "amharic text"})
        self.assertIsNone(languages["none"])
        self.assertFalse(OLD_KEY.search(json.dumps(languages)))
        self.assertFalse(OLD_KEY.search(json.dumps(section)))
        panel = section["panels"][0]
        self.assertEqual(panel["panel-id"], "location_widgets")
        widget = panel["widgets"][0]
        self.assertEqual(widget["widget-data-validation"]["patternMessage"], "validation_first_name")
        self.assertEqual(widget["widget-data-options"]["minDateMessage"], "validation_date_of_birth_min")

    async def test_running_it_twice_changes_nothing_more(self):
        await self.run_script(CLEANUP)
        once = await self.state()
        await self.run_script(CLEANUP)
        self.assertEqual(await self.state(), once)

    async def test_the_location_seed_renames_the_old_panel_instead_of_adding_a_second_one(self):
        await self.run_script(LOCATION)
        _, section = await self.state()
        self.assertEqual([panel["panel-id"] for panel in section["panels"]], ["location_widgets"])


if __name__ == "__main__":
    unittest.main()
