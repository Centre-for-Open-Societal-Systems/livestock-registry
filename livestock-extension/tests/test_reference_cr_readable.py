"""A pending Farmer-reference ADD opens before its Farmer record exists."""
import importlib
import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

PACKAGE = os.environ.get("REGISTRY_EXTENSION_MODULE", "openg2p_registry_livestock_extension")

try:
    native = importlib.import_module(PACKAGE + ".farmer_reference.native")
except ImportError:  # the platform runtime is only in the native test image
    native = None


def session_for(managed, change_request, farmer):
    session = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = managed
    session.execute = AsyncMock(return_value=result)
    session.get = AsyncMock(side_effect=lambda model, key: change_request if model is native.G2PRegisterChangeRequest else farmer)
    return session


@unittest.skipUnless(native, "Requires the OpenG2P runtime")
class PendingReferenceReadableTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.service = object.__new__(native.ReferenceChangeRequestService)
        self.change_request = SimpleNamespace(change_request_id="cr-1", internal_record_id="local-farmer-1")
        models = SimpleNamespace(G2PRegisterFarmer=type("G2PRegisterFarmer", (), {}))
        patcher = patch.object(native, "domain_models", return_value=models)
        patcher.start()
        self.addCleanup(patcher.stop)

    async def test_pending_add_without_a_farmer_record_is_readable(self):
        session = session_for(SimpleNamespace(action="ADD"), self.change_request, None)
        with patch.object(native.G2PRegisterChangeRequestService, "_ensure_change_request_readable",
                          new=AsyncMock(side_effect=AssertionError("native check must not run"))):
            result = await self.service._ensure_change_request_readable("cr-1", None, session)
        self.assertIs(result, self.change_request)

    async def test_approved_add_with_its_farmer_record_keeps_the_native_check(self):
        session = session_for(SimpleNamespace(action="ADD"), self.change_request, object())
        native_check = AsyncMock(return_value="native")
        with patch.object(native.G2PRegisterChangeRequestService, "_ensure_change_request_readable", new=native_check):
            result = await self.service._ensure_change_request_readable("cr-1", None, session)
        self.assertEqual(result, "native")
        native_check.assert_awaited_once()

    async def test_any_other_request_keeps_the_native_check(self):
        session = session_for(None, None, None)
        native_check = AsyncMock(return_value="native")
        with patch.object(native.G2PRegisterChangeRequestService, "_ensure_change_request_readable", new=native_check):
            result = await self.service._ensure_change_request_readable("cr-2", None, session)
        self.assertEqual(result, "native")
        native_check.assert_awaited_once_with("cr-2", None, session)


if __name__ == "__main__":
    unittest.main()
