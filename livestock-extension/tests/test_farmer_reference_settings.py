"""Farmer-reference settings: the new variable names win, the old ones still work and warn once."""
import importlib
import logging
import os
import sys
import unittest
from unittest import mock

PACKAGE = os.environ.get("REGISTRY_EXTENSION_MODULE", "openg2p_registry_livestock_extension")
sys.modules.setdefault("openg2p_registry_extensions", importlib.import_module(PACKAGE))
configuration = importlib.import_module(PACKAGE + ".farmer_reference.configuration")
approval_context = importlib.import_module(PACKAGE + ".farmer_reference.approval_context")

NEW = "REGISTRY_FARMER_REFERENCE_"
OLD = "COSS_FARMER_"


class SettingTests(unittest.TestCase):
    def setUp(self):
        configuration._legacy_names_warned.clear()

    def test_the_new_name_is_read(self):
        with mock.patch.dict(os.environ, {NEW + "SOURCE_ID": "new"}, clear=True):
            self.assertEqual(configuration.setting("SOURCE_ID"), "new")

    def test_the_new_name_wins_over_the_old_one(self):
        with mock.patch.dict(os.environ, {NEW + "SOURCE_ID": "new", OLD + "SOURCE_ID": "old"}, clear=True):
            with self.assertNoLogs(configuration._logger, logging.WARNING):
                self.assertEqual(configuration.setting("SOURCE_ID"), "new")

    def test_the_old_name_is_used_and_warns_once_per_process(self):
        with mock.patch.dict(os.environ, {OLD + "SOURCE_ID": "old"}, clear=True):
            with self.assertLogs(configuration._logger, logging.WARNING) as logged:
                self.assertEqual(configuration.setting("SOURCE_ID"), "old")
                self.assertEqual(configuration.setting("SOURCE_ID"), "old")
            self.assertEqual(len(logged.records), 1)
            self.assertIn(NEW + "SOURCE_ID", logged.output[0])

    def test_the_default_applies_when_neither_is_set(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(configuration.setting("SOURCE_ID"))
            self.assertEqual(configuration.setting("SIGNING_ALGORITHM", "RS256"), "RS256")

    def test_the_source_id_resolves_under_either_name_for_the_approval_context(self):
        for name in (NEW, OLD):
            with self.subTest(prefix=name), mock.patch.dict(os.environ, {name + "SOURCE_ID": "source"}, clear=True):
                context = approval_context.approval_context(
                    "UPDATE", response_digest="digest", source_system="source",
                    configured_source_system=configuration.setting("SOURCE_ID", ""))
                self.assertEqual(context["source"], approval_context.FARMER_REGISTRY_SOURCE)

    def test_no_other_module_reads_the_variables_directly(self):
        root = os.path.dirname(configuration.__file__)
        for name in sorted(os.listdir(root)):
            if name.endswith(".py") and name != "configuration.py":
                with open(os.path.join(root, name), encoding="utf-8") as handle:
                    source = handle.read()
                with self.subTest(module=name):
                    self.assertNotIn(OLD, source)
                    self.assertNotIn("os.environ", source)


if __name__ == "__main__":
    unittest.main()
