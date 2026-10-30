"""Both WebSub signature header names are accepted on webhook paths."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from openg2p_registry_connector_extension import webhook_signature as ws  # noqa: E402

LEGACY, CURRENT = b"x-hub-signature", b"x-hub-signature-256"


def run(path, headers, scope_type="http"):
    seen = {}

    async def app(scope, receive, send):
        seen["headers"] = dict(scope["headers"])

    mw = ws.WebhookSignatureCompatMiddleware(app)
    asyncio.run(mw({"type": scope_type, "path": path, "headers": headers}, None, None))
    return seen["headers"]


def test_legacy_copied_to_256():
    h = run("/webhook/x", [(LEGACY, b"sha256=abc")])
    assert h[CURRENT] == b"sha256=abc" and h[LEGACY] == b"sha256=abc"


def test_256_copied_to_legacy():
    h = run("/webhook", [(CURRENT, b"sha256=abc")])
    assert h[LEGACY] == b"sha256=abc"


def test_not_overwritten_when_both_present():
    h = run("/webhook/x", [(LEGACY, b"sha256=old"), (CURRENT, b"sha256=new")])
    assert h[LEGACY] == b"sha256=old" and h[CURRENT] == b"sha256=new"


def test_other_paths_ignored():
    assert CURRENT not in run("/admin/x", [(LEGACY, b"sha256=abc")])
    assert LEGACY not in run("/admin/x", [(CURRENT, b"sha256=abc")])


def test_value_without_prefix_ignored():
    assert CURRENT not in run("/webhook/x", [(LEGACY, b"abc")])
    assert LEGACY not in run("/webhook/x", [(CURRENT, b"md5=abc")])


def test_header_name_case_insensitive_and_non_http_untouched():
    assert run("/webhook/x", [(b"X-Hub-Signature", b"sha256=a")])[CURRENT] == b"sha256=a"
    assert CURRENT not in run("/webhook/x", [(LEGACY, b"sha256=a")], scope_type="websocket")


def test_install_once_on_fastapi_app():
    from fastapi import FastAPI

    app = FastAPI()
    ws.install(app)
    ws.install(app)
    assert sum(m.cls is ws.WebhookSignatureCompatMiddleware for m in app.user_middleware) == 1
