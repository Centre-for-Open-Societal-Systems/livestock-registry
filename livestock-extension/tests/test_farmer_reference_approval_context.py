"""change_type and source: the facts an approval policy tests, never a decision."""
import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock

SOURCE = next((Path(__file__).resolve().parents[1] / "src").glob("openg2p_registry_*_extension"))
# Absolute-name load: the module has no relative imports and no platform imports.
spec = importlib.util.spec_from_file_location("approval_context_under_test", SOURCE / "farmer_reference" / "approval_context.py")
context = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = context
spec.loader.exec_module(context)

SOURCE_SYSTEM = "central-farmer"
DIGEST = "signed-response-digest"


class ApprovalContextTests(unittest.TestCase):
    def build(self, action, **overrides):
        values = {"response_digest": DIGEST, "source_system": SOURCE_SYSTEM, "configured_source_system": SOURCE_SYSTEM}
        values.update(overrides)
        return context.approval_context(action, **values)

    def test_verified_add_and_update_carry_their_action_and_the_farmer_registry_source(self):
        self.assertEqual(self.build("ADD"), {"change_type": "ADD", "source": "farmer-registry"})
        self.assertEqual(self.build("UPDATE"), {"change_type": "UPDATE", "source": "farmer-registry"})

    def test_anything_unproven_is_unverified_so_a_human_stays_in_the_loop(self):
        for overrides in ({"response_digest": ""}, {"response_digest": None}, {"source_system": "other-system"},
                          {"source_system": ""}, {"configured_source_system": ""}, {"configured_source_system": "  "}):
            with self.subTest(overrides=overrides):
                self.assertEqual(self.build("UPDATE", **overrides), {"change_type": "UPDATE", "source": "unverified"})

    def test_configured_source_defaults_to_the_deployment_variable(self):
        with mock.patch.dict("os.environ", {context.SOURCE_ID_VARIABLE: " " + SOURCE_SYSTEM + " "}):
            self.assertEqual(context.approval_context("UPDATE", response_digest=DIGEST, source_system=SOURCE_SYSTEM)["source"],
                             "farmer-registry")
        with mock.patch.dict("os.environ", clear=True):
            self.assertEqual(context.approval_context("UPDATE", response_digest=DIGEST, source_system=SOURCE_SYSTEM)["source"],
                             "unverified")

    def test_the_keys_are_exactly_those_the_binding_declares(self):
        self.assertEqual(sorted(self.build("ADD")), sorted(context.CONTEXT_FIELD_NAMES))
        binding = (SOURCE / "meta_data/register-metadata/zzz_farmer_reference_awe.sql").read_text()
        self.assertIn('\'["change_type", "source"]\'', binding)
        self.assertEqual(context.CONTEXT_FIELD_NAMES, ["change_type", "source"])

    def test_workflow_always_sends_them_and_keeps_the_single_native_call(self):
        # The platform filters the context by the binding's names; the workflow
        # must not decide anything itself, so it only merges these two keys.
        text = (SOURCE / "farmer_reference" / "workflow.py").read_text()
        self.assertIn("approval_context(request.action, response_digest=request.response_digest", text)
        self.assertIn("start_change_request_workflow(session, change_request, [context]", text)
        self.assertNotIn("skip_if", text)
        self.assertNotIn("auto_approve", text.lower())


if __name__ == "__main__":
    unittest.main()
