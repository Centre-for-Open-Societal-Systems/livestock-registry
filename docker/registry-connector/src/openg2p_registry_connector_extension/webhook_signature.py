"""Accept both WebSub signature header names on webhook requests.

The upstream verifier (``webhooks/verifiers.py``, ``hmac_sha256``) reads
``X-Hub-Signature-256``; hubs on older connector code sign with
``X-Hub-Signature: sha256=<hex hmac>``. This middleware makes the two names
interchangeable for paths under ``/webhook``. It only copies a header; the HMAC is
still verified by the upstream code.
"""

PREFIX = "sha256="
PATH_PREFIX = "/webhook"
LEGACY = b"x-hub-signature"
CURRENT = b"x-hub-signature-256"
_MARK = "webhook_signature_compat_installed"


def _alias(headers: list) -> list:
    names = {k.lower() for k, _ in headers}
    for src, dst in ((LEGACY, CURRENT), (CURRENT, LEGACY)):
        if dst in names or src not in names:
            continue
        value = next(v for k, v in headers if k.lower() == src)
        if value.startswith(PREFIX.encode()):
            return [*headers, (dst, value)]
    return headers


class WebhookSignatureCompatMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope.get("path", "").startswith(PATH_PREFIX):
            scope = {**scope, "headers": _alias(list(scope.get("headers", [])))}
        await self.app(scope, receive, send)


def install(app) -> None:
    """Add the middleware to the connector's FastAPI app once."""
    if getattr(app.state, _MARK, False):
        return
    app.add_middleware(WebhookSignatureCompatMiddleware)
    setattr(app.state, _MARK, True)
