import ast
import asyncio
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "livestock-extension/src/openg2p_registry_livestock_extension"
GUARDED = {
    "farmer_reference/native.py": ["ReferenceIntakeService", "ReferenceChangeRequestService"],
}
WORKFLOW_METHODS = {"approve_submission_with_session", "approve_change_request_from_awe_webhook",
                    "_approve_change_request_core"}


def _guard():
    spec = importlib.util.spec_from_file_location("direct_approval_under_test", PACKAGE / "direct_approval.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(coroutine):
    return asyncio.run(coroutine)


class _Base:
    """Stands in for the platform service: records the calls the guard lets through."""

    def __init__(self):
        self.calls = []

    async def approve_submission(self, submission_id, approved_by):
        self.calls.append("approve_submission")

    async def approve_change_request(self, change_request_id, approved_by=None):
        self.calls.append("approve_change_request")

    async def approve_submission_with_session(self, submission_id, session, approved_by=None):
        self.calls.append("approve_submission_with_session")
        return "approved"

    async def approve_change_request_from_awe_webhook(self, change_request_id, session, approved_by=None):
        self.calls.append("approve_change_request_from_awe_webhook")
        return "applied"


def _service():
    class Guarded(_guard().DirectApprovalClosed, _Base):
        pass

    return Guarded()


def _refusal(coroutine):
    try:
        _run(coroutine)
    except Exception as error:  # the platform exception when installed, the local one here
        return error
    raise AssertionError("the direct approval was not refused")


def test_direct_intake_approval_is_refused_and_never_reaches_the_platform():
    service = _service()
    error = _refusal(service.approve_submission("submission-1", "someone"))
    assert error.code == "AWE_APPROVAL_REQUIRED"
    assert "approval task" in error.message
    assert service.calls == []


def test_direct_change_request_approval_is_refused_and_never_reaches_the_platform():
    service = _service()
    error = _refusal(service.approve_change_request("change-1", "someone"))
    assert error.code == "AWE_APPROVAL_REQUIRED"
    assert service.calls == []


def test_the_refusal_holds_for_any_arguments():
    service = _service()
    _refusal(service.approve_submission("submission-1", approved_by="admin"))
    _refusal(service.approve_change_request(change_request_id="change-1", approved_by="admin"))
    assert service.calls == []


def test_the_workflow_engine_decisions_still_reach_the_platform():
    service = _service()
    assert _run(service.approve_submission_with_session("submission-1", object())) == "approved"
    assert _run(service.approve_change_request_from_awe_webhook("change-1", object())) == "applied"
    assert service.calls == ["approve_submission_with_session", "approve_change_request_from_awe_webhook"]


def test_the_guard_defines_only_the_two_direct_calls():
    tree = ast.parse((PACKAGE / "direct_approval.py").read_text())
    mixin = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "DirectApprovalClosed")
    defined = {n.name for n in mixin.body if isinstance(n, ast.AsyncFunctionDef)}
    assert defined == {"approve_submission", "approve_change_request"}
    assert not defined & WORKFLOW_METHODS


def _classes(path):
    tree = ast.parse((PACKAGE / path).read_text())
    return {n.name: [ast.unparse(b) for b in n.bases] for n in tree.body if isinstance(n, ast.ClassDef)}


def test_every_installed_intake_and_change_request_service_carries_the_guard_first():
    for path, names in GUARDED.items():
        classes = _classes(path)
        for name in names:
            assert classes[name][0] == "DirectApprovalClosed", f"{path}:{name} must put the guard first"


def _methods(path):
    tree = ast.parse((PACKAGE / path).read_text())
    return {n.name: {m.name for m in n.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))}
            for n in tree.body if isinstance(n, ast.ClassDef)}


def test_no_guarded_service_redefines_a_direct_call():
    # A redefinition would run before the guard: it could look the record up
    # first, so a made-up id would answer "not found" and a real one would not.
    for path, names in GUARDED.items():
        methods = _methods(path)
        for name in names:
            assert not methods[name] & {"approve_submission", "approve_change_request"}, f"{path}:{name}"


def test_a_made_up_id_gets_the_same_refusal_as_a_real_one():
    class Looking(_Base):
        async def approve_submission(self, submission_id, approved_by):
            raise LookupError("INTAKE_FORM_NOT_FOUND: " + submission_id)

    class Guarded(_guard().DirectApprovalClosed, Looking):
        pass

    for submission_id in ("00000000-0000-0000-0000-000000000000", "a-real-looking-id"):
        error = _refusal(Guarded().approve_submission(submission_id, "admin"))
        assert "NOT_FOUND" not in str(error)
        assert getattr(error, "code", "") == "AWE_APPROVAL_REQUIRED"
