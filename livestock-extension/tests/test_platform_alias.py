"""The platform alias and the real package name must share one module object.

The platform publishes the selected extension as ``openg2p_registry_extensions``
by assigning the package in sys.modules; its ingestion classifier then imports
``openg2p_registry_extensions.register_domain.models`` inside the celery worker,
which loaded the same file under the real name at startup. Without the alias
finder that second execution declares every mapped table twice.
"""
import importlib
import importlib.util
import os
import sys
import unittest

PACKAGE = os.environ.get("REGISTRY_EXTENSION_MODULE", "openg2p_registry_livestock_extension")
ALIAS = "openg2p_registry_extensions"


def _platform_dependencies_available():
    return importlib.util.find_spec("openg2p_registry_core") is not None


class PlatformAliasTests(unittest.TestCase):
    def setUp(self):
        self.package = importlib.import_module(PACKAGE)
        sys.modules[ALIAS] = self.package

    def test_light_submodule_is_shared_between_both_names(self):
        real = importlib.import_module(PACKAGE + ".farmer_reference.profile")
        aliased = importlib.import_module(ALIAS + ".farmer_reference.profile")
        self.assertIs(aliased, real)
        self.assertEqual(real.__name__, PACKAGE + ".farmer_reference.profile")
        self.assertEqual(real.__spec__.name, PACKAGE + ".farmer_reference.profile")
        self.assertIs(sys.modules[ALIAS + ".farmer_reference"], sys.modules[PACKAGE + ".farmer_reference"])

    def test_alias_first_import_loads_the_real_module_once(self):
        for name in list(sys.modules):
            if name.endswith(".farmer_reference.messages"):
                del sys.modules[name]
        aliased = importlib.import_module(ALIAS + ".farmer_reference.messages")
        self.assertIs(aliased, sys.modules[PACKAGE + ".farmer_reference.messages"])
        self.assertEqual(aliased.__name__, PACKAGE + ".farmer_reference.messages")

    def test_finder_ignores_foreign_alias_targets(self):
        sys.modules[ALIAS] = sys
        try:
            finder = next(f for f in sys.meta_path if type(f).__name__ == "_PlatformAliasFinder")
            self.assertIsNone(finder.find_spec(ALIAS + ".register_domain.models"))
        finally:
            sys.modules[ALIAS] = self.package

    @unittest.skipUnless(_platform_dependencies_available(), "Requires the platform image")
    def test_domain_models_import_under_both_names_without_redefining_tables(self):
        real = importlib.import_module(PACKAGE + ".register_domain.models")
        aliased = importlib.import_module(ALIAS + ".register_domain.models")
        self.assertIs(aliased, real)
        self.assertIs(aliased.G2PRegisterFarmer, real.G2PRegisterFarmer)
        self.assertIn("g2p_register_farmers", real.G2PRegisterFarmer.metadata.tables)
