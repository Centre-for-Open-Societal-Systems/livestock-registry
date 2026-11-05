"""Count actual native widgets after full/repeated seed; never hide duplicates."""
import importlib
import os
import unittest
from collections import Counter
from copy import deepcopy
from pathlib import Path

PRODUCT = "livestock"
IDS = {"farmer_id", "fayda_fin", "fayda_fan_id", "farmer_reference_status"}


def widgets(node):
    if isinstance(node, dict):
        if "widget" in node:
            yield node
        for value in node.values():
            yield from widgets(value)
    elif isinstance(node, list):
        for value in node:
            yield from widgets(value)


def assert_identity(test, ui):
    counts = Counter(w.get("widget-id") for w in widgets(ui))
    test.assertEqual(counts, Counter({key: 1 for key in IDS}))


class WidgetCounterTests(unittest.TestCase):
    def test_real_duplicate_is_rejected_instead_of_counting_distinct_ids(self):
        ui = {"panels": [{"widgets": [{"widget": "text", "widget-id": key} for key in sorted(IDS)]}]}
        assert_identity(self, ui)
        ui["panels"][0]["widgets"].append(deepcopy(ui["panels"][0]["widgets"][0]))
        with self.assertRaises(AssertionError):
            assert_identity(self, ui)


@unittest.skipUnless(os.environ.get("FARMER_TEST_DATABASE_URL"), "Requires disposable PostgreSQL")
class PopupIdentityMetadataTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.fixture = importlib.import_module("test_farmer_reference_native").NativeReferenceTests()
        await self.fixture.asyncSetUp()

    async def asyncTearDown(self):
        await self.fixture.asyncTearDown()

    async def replay(self, paths):
        async with self.fixture.engine.begin() as connection:
            raw = await connection.get_raw_connection()
            for path in paths:
                sql = path.read_text(encoding="utf-8").replace('"public".', '"'+self.fixture.schema+'".').replace("public.", '"'+self.fixture.schema+'".')
                await raw.driver_connection.execute(sql)

    async def snapshot(self):
        from sqlalchemy import select
        from openg2p_registry_core.models import G2PRegisterSection
        async with self.fixture.sessions() as session:
            return {row.section_id: deepcopy(row.section_ui_schema) for row in
                    (await session.execute(select(G2PRegisterSection))).scalars()}

    async def test_full_seed_twice_and_final_patch_twice_preserve_all_form_contracts(self):
        from sqlalchemy import select, update
        from openg2p_registry_core.models import G2PIntakeFormUITabSection, G2PRegisterUITabSection
        package = importlib.import_module("openg2p_registry_"+PRODUCT+"_extension")
        paths = sorted((Path(package.__file__).parent/"meta_data/register-metadata").glob("*.sql"))
        final = next(p for p in paths if p.name == "zzzzzzzz_popup_only_fin.sql")
        await self.replay([p for p in paths if p != final])
        # An existing New Dev binding has the same stable row/tab IDs but
        # points at the legacy Farmer section. Base ON CONFLICT DO NOTHING
        # deliberately preserves it; the bounded identity patch must migrate
        # this known binding without touching registered Farmer sections.
        async with self.fixture.sessions.begin() as session:
            await session.execute(update(G2PIntakeFormUITabSection).where(
                G2PIntakeFormUITabSection.tab_section_id == "intake_tab_section_1"
            ).values(section_id="livestock_farmer_identity_section_01"))
        split = next(p for p in paths if p.name == "zzzzzzz_identity_section_split.sql")
        await self.replay([split])
        async with self.fixture.sessions() as session:
            migrated = await session.get(G2PIntakeFormUITabSection, "intake_tab_section_1")
            self.assertEqual(migrated.section_id, "livestock_intake_identity_section_01")
            self.assertEqual(migrated.tab_id, "0ebdc221-187d-5df6-9dc3-c6f4c4ee160e")
        # Reproduce the competing legacy alias binding found on restored New
        # Dev. Native resolution must stay unique, while the full old row is
        # retained in extension-owned audit history.
        from uuid import uuid4
        from sqlalchemy import func
        from openg2p_registry_core.models import G2PRegistryAwePolicyConfiguration
        from openg2p_registry_core.services.g2p_awe_policy_configuration_service import G2PAwePolicyConfigurationService
        archive_model = importlib.import_module("openg2p_registry_extensions.farmer_reference.models").ApprovalBindingArchive
        root_id = "6b06a95a-9a6c-5a33-a33d-c1625716c59c" if PRODUCT == "cropsown" else "997676d3-7008-59f9-b23e-613ad79bbb08"
        old_id, unrelated_id = str(uuid4()), str(uuid4())
        async with self.fixture.sessions.begin() as session:
            session.add_all([
                G2PRegistryAwePolicyConfiguration(awe_policy_config_id=old_id,
                    policy_scope="REGISTER", register_id=root_id,
                    policy_type="change_request", policy_key="legacy.custom.policy",
                    context_field_names=["legacy_custom_approvers"]),
                G2PRegistryAwePolicyConfiguration(awe_policy_config_id=unrelated_id,
                    policy_scope="REGISTER", register_id=root_id,
                    policy_type="synthetic.unrelated", policy_key="unrelated.keep",
                    context_field_names=["unrelated_context"])])
        await self.replay(paths)
        async with self.fixture.sessions() as session:
            self.assertIsNone(await session.get(G2PRegistryAwePolicyConfiguration, old_id))
            old_snapshots = (await session.execute(select(archive_model).where(
                archive_model.binding_id == old_id))).scalars().all()
            self.assertTrue(any(row.original_binding["policy_key"] == "legacy.custom.policy"
                and row.original_binding["context_field_names"] == ["legacy_custom_approvers"]
                for row in old_snapshots))
            unrelated = await session.get(G2PRegistryAwePolicyConfiguration, unrelated_id)
            self.assertEqual(unrelated.policy_key, "unrelated.keep")
            self.assertEqual(unrelated.context_field_names, ["unrelated_context"])
            policy = await G2PAwePolicyConfigurationService.get_component().find_effective_policy_configuration(
                session, register_id=root_id, policy_type="registry.change_request")
            self.assertEqual(policy.policy_key, f"registry.change_request.{PRODUCT}.default")
            archive_count = await session.scalar(select(func.count()).select_from(archive_model))
        before = await self.snapshot()
        await self.replay([final, final])
        first = await self.snapshot()
        expected = ({"cropsown_intake_record_section_01", "cropsown_common_intake_record_section_01"}
                    if PRODUCT == "cropsown" else {"livestock_intake_identity_section_01"})
        for _ in range(2):
            await self.replay(paths)
            current = await self.snapshot()
            async with self.fixture.sessions() as session:
                self.assertEqual(await session.scalar(select(func.count()).select_from(archive_model)), archive_count)
            self.assertEqual(current, first)
            for section in expected:
                assert_identity(self, current[section])
                fan = next(w for w in widgets(current[section]) if w.get("widget-id") == "fayda_fan_id")
                self.assertNotEqual(fan.get("widget-readonly"), True)
                self.assertNotEqual(fan.get("widget"), "display")
            async with self.fixture.sessions() as session:
                intake = set((await session.execute(select(G2PIntakeFormUITabSection.section_id))).scalars())
                registered = set((await session.execute(select(G2PRegisterUITabSection.section_id))).scalars())
            self.assertTrue(expected <= intake)
            for section in intake | registered:
                ui = current[section]
                # Walk the actual arrays once; SQL DISTINCT would mask the regression.
                for w in widgets(ui):
                    path = w.get("widget-data-path")
                    if w.get("widget-id") == "fayda_fin" or isinstance(path, str) and path.endswith(".fayda_fin"):
                        self.assertEqual(w.get("widget"), "display")
                        self.assertIs(w.get("widget-readonly"), True)
                        self.assertIs(w.get("widget-required"), False)
                # Preserve every stored field path, including source projections.
                original_paths = {str(w.get("widget-data-path")) for w in widgets(before[section])}
                self.assertEqual({str(w.get("widget-data-path")) for w in widgets(ui)}, original_paths)
            record = PRODUCT+"_"+PRODUCT+"_record_section_01"
            self.assertIn(record, registered)
            counts = Counter(w.get("widget-id") for w in widgets(current[record]))
            for identity_id in IDS:
                self.assertEqual(counts[identity_id], 1, (record, identity_id, counts))
            self.assertTrue(any(w.get("widget-id") == "farmer_name" for w in widgets(current[record])))

    async def test_extractor_handles_nested_arrays_and_real_duplicate_ids(self):
        import json
        package = importlib.import_module("openg2p_registry_"+PRODUCT+"_extension")
        split = Path(package.__file__).parent/"meta_data/register-metadata/zzzzzzz_identity_section_split.sql"
        function_sql = split.read_text(encoding="utf-8").split("$$;", 1)[0]+"$$;"
        fixture = {"panels": [{"widgets": [{"widget": "text", "widget-id": "farmer_id", "marker": "first"},
                    {"widget": "text", "widget-id": "farmer_id", "marker": "duplicate"}]},
                    {"panels": [{"widgets": [{"widget": "display", "widget-id": "fayda_fin"}]}]}]}
        async with self.fixture.engine.begin() as connection:
            raw = await connection.get_raw_connection()
            await raw.driver_connection.execute(function_sql)
            value = await raw.driver_connection.fetchval("SELECT pg_temp.oan_widgets($1::jsonb, ARRAY['farmer_id','fayda_fin'])", json.dumps(fixture))
        result = json.loads(value) if isinstance(value, str) else value
        self.assertEqual([w["widget-id"] for w in result], ["farmer_id", "fayda_fin"])
        self.assertEqual(result[0]["marker"], "first")

    async def test_final_dedup_preserves_unrelated_widgets_and_null_array_values(self):
        import json
        package = importlib.import_module("openg2p_registry_"+PRODUCT+"_extension")
        final = Path(package.__file__).parent/"meta_data/register-metadata/zzzzzzzz_popup_only_fin.sql"
        functions = final.read_text(encoding="utf-8").split("-- Earlier popup patches", 1)[1]
        functions = "-- Earlier popup patches"+functions.split("UPDATE g2p_register_sections", 1)[0]
        fixture = {"widgets": [{"widget":"profile", "widget-id":"profile", "values":[None]},
                    {"widget":"text", "widget-id":"farmer_id", "widget-data-path":"domain.farmer_id"},
                    {"widget":"text", "widget-id":"farmer_id", "widget-data-path":"domain.farmer_id"},
                    {"widget":"display", "widget-id":"farmer_name"}]}
        async with self.fixture.engine.begin() as connection:
            raw = await connection.get_raw_connection()
            await raw.driver_connection.execute(functions)
            result = await raw.driver_connection.fetchval("SELECT pg_temp.oan_unique_identity_widgets($1::jsonb)->'node'", json.dumps(fixture))
        value = json.loads(result) if isinstance(result, str) else result
        self.assertEqual(value["widgets"], [fixture["widgets"][0], fixture["widgets"][1], fixture["widgets"][3]])
