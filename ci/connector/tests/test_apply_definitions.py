"""Unit tests for chart/files/apply_definitions.py (no network, no cluster)."""

import importlib.util
import json
import pathlib
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("apply_definitions", ROOT / "chart/files/apply_definitions.py")
ad = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ad)

RECEIVER = {
    "name": "Receiver", "platform": "internal_registry", "transport_type": "websub",
    "g2p_sender_id": "S", "g2p_register_mnemonic": "Farmer", "webhook_path_slug": "slug-1",
    "webhook_secret_from": {"secret": "s", "key": "k"},
    "source_config": {"hub_url": "http://hub", "topics": ["t"]},
}
ROW = {"connector_id": "abc", "name": "Receiver", "platform": "internal_registry",
       "transport_type": "websub", "g2p_sender_id": "S", "g2p_register_mnemonic": "Farmer",
       "webhook_path_slug": "slug-1", "source_config_json": '{"topics": ["t"], "hub_url": "http://hub"}'}


class PlanTests(unittest.TestCase):
    def test_create_when_missing(self):
        plan = ad.plan_definition(RECEIVER, 0, [], {"CD_0_WEBHOOK_SECRET": "x"})
        self.assertEqual(plan["action"], "create")
        self.assertEqual(plan["body"]["webhook_secret"], "x")
        self.assertEqual(json.loads(plan["body"]["source_config_json"])["topics"], ["t"])

    def test_create_without_secret_fails(self):
        with self.assertRaises(ad.ApplyError):
            ad.plan_definition(RECEIVER, 0, [], {})

    def test_existing_keeps_stored_secret_when_env_empty(self):
        plan = ad.plan_definition(RECEIVER, 0, [ROW], {})
        self.assertNotIn("webhook_secret", plan["body"])
        self.assertEqual(plan["notes"]["missing_secrets"], ["webhook_secret"])

    def test_unchanged_ignores_json_key_order(self):
        plan = ad.plan_definition(RECEIVER, 0, [ROW], {})
        self.assertEqual(plan["action"], "unchanged")

    def test_patch_on_difference(self):
        changed = dict(RECEIVER, source_config={"hub_url": "http://hub", "topics": ["u"]})
        plan = ad.plan_definition(changed, 0, [ROW], {})
        self.assertEqual(plan["action"], "patch")
        self.assertEqual(plan["changed"], ["source_config_json"])

    def test_patch_when_secret_present(self):
        plan = ad.plan_definition(RECEIVER, 0, [ROW], {"CD_0_WEBHOOK_SECRET": "x"})
        self.assertEqual(plan["action"], "patch")

    def test_transport_change_is_refused(self):
        with self.assertRaises(ad.ApplyError):
            ad.plan_definition(dict(RECEIVER, transport_type="webhook"), 0, [ROW], {})

    def test_match_by_previous_name_and_slug(self):
        renamed = dict(RECEIVER, name="New", previous_names=["Receiver"])
        self.assertEqual(ad.find_existing(renamed, [ROW])["connector_id"], "abc")
        by_slug = dict(RECEIVER, name="Other")
        self.assertEqual(ad.find_existing(by_slug, [ROW])["connector_id"], "abc")

    def test_auth_secret_all_or_nothing(self):
        odk = {"name": "ODK", "platform": "odk_central", "transport_type": "odk_central",
               "g2p_sender_id": "L", "g2p_register_mnemonic": "L",
               "auth_secret_from": {"email": {}, "password": {}}}
        body, notes = ad.desired_body(odk, 2, {"CD_2_AUTH_EMAIL": "e"})
        self.assertNotIn("auth_secret_json", body)
        self.assertEqual(notes["missing_secrets"], ["auth_secret_json"])
        body, _ = ad.desired_body(odk, 2, {"CD_2_AUTH_EMAIL": "e", "CD_2_AUTH_PASSWORD": "p"})
        self.assertEqual(json.loads(body["auth_secret_json"]), {"email": "e", "password": "p"})

    def test_subscription_rules(self):
        self.assertTrue(ad.wants_subscription(RECEIVER))
        self.assertFalse(ad.wants_subscription(dict(RECEIVER, subscribe=False)))
        self.assertFalse(ad.wants_subscription(dict(RECEIVER, enabled=False)))
        self.assertFalse(ad.wants_subscription(dict(RECEIVER, transport_type="odk_central")))


class MainTests(unittest.TestCase):
    def run_main(self, rows, definitions, retired=()):
        calls = []

        def fake_http(method, url, token=None, body=None, **kw):
            calls.append((method, url.split("//", 1)[1].split("/", 1)[1], body))
            if method == "GET" and url.endswith("/connectors"):
                return 200, rows
            if method == "POST" and url.endswith("/connectors"):
                return 201, {"connector_id": "new1"}
            if url.endswith("sync-subscriptions"):
                return 200, {"all_subscribe_ok": True, "topics_attempted": ["t"], "hub_url": "h"}
            return 200, {}

        config = {"apiBase": "http://api", "adminAuth": {"enabled": False},
                  "definitions": definitions, "retired": list(retired)}
        with mock.patch.object(ad, "http", fake_http), mock.patch.object(ad, "wait_for_api"), \
                mock.patch.object(ad, "open", mock.mock_open(read_data=json.dumps(config)), create=True), \
                mock.patch.dict(ad.os.environ, {"CD_0_WEBHOOK_SECRET": "x"}):
            code = ad.main()
        return code, calls

    def test_create_then_subscribe(self):
        code, calls = self.run_main([], [RECEIVER])
        self.assertEqual(code, 0)
        self.assertEqual([c[0] for c in calls], ["GET", "POST", "POST"])
        self.assertTrue(calls[2][1].endswith("connectors/new1/websub/sync-subscriptions"))

    def test_second_run_patches_and_subscribes_again(self):
        code, calls = self.run_main([ROW], [RECEIVER])
        self.assertEqual(code, 0)
        self.assertEqual([c[0] for c in calls], ["GET", "PATCH", "POST"])

    def test_retired_row_is_deleted_and_missing_one_is_not(self):
        other = dict(ROW, connector_id="old", name="Old")
        code, calls = self.run_main([ROW, other], [], retired=["Old", "Gone"])
        self.assertEqual(code, 0)
        self.assertEqual([c[0] for c in calls], ["GET", "DELETE"])

    def test_failure_returns_nonzero(self):
        code, _ = self.run_main([], [dict(RECEIVER, g2p_sender_id=None)])
        self.assertEqual(code, 1)


class ValuesTests(unittest.TestCase):
    def test_definitions_files_hold_no_secret_values_and_names_are_unique(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed")
        for name in ("definitions.newdev.yaml", "definitions.staging.yaml"):
            data = yaml.safe_load((ROOT / name).read_text())["connectorDefinitions"]
            names = [d["name"] for d in data["definitions"]]
            self.assertEqual(len(names), len(set(names)), name)
            slugs = [d["webhook_path_slug"] for d in data["definitions"] if d.get("webhook_path_slug")]
            self.assertEqual(len(slugs), len(set(slugs)), name)
            for d in data["definitions"]:
                self.assertNotIn("webhook_secret", d)
                self.assertNotIn("auth_secret_json", d)
                if d["transport_type"] == "websub":
                    self.assertIn(d["webhook_path_slug"], d["source_config"]["callback_url"])


if __name__ == "__main__":
    unittest.main()
