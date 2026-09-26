"""HTTP endpoint AWE calls (server-to-server) to resolve WHO can approve a
given stage of the Livestock hierarchical Kebele -> Woreda -> Zone -> Region
approval chain, scoped to the specific location the record being approved
carries at that level. Paired with the 4 approval_stage/approver_rule rows
(rule_type="http") on the registry.intake_form.livestock AWE policy — see
[[livestock-4-level-approval-chain]] plan and
docker/local-dev/awe-seed/20_approval_stage.sql.

A custom controller, not a core-patch — same reasoning as
G2PAnimalBulkImportController: the platform's own BaseController +
app_registry pattern is already an extension point, no core file needs
touching to add a new route.
"""

import logging
import os

from fastapi import Request
from openg2p_fastapi_common.controller import BaseController
from starlette.responses import JSONResponse

from ..services.approver_resolver_service import resolve_approvers

_logger = logging.getLogger("g2p-approver-resolver")


class G2PApproverResolverController(BaseController):
    """Deliberately undecorated with @require_permissions/@requires_auth —
    same as the platform's own G2PAWEWebhookController
    (openg2p_registry_staff_api/controllers/g2p_awe_webhook_controller.py,
    "Inbound AWE ... webhooks (HMAC auth, no JWT)"): ValidateAndRefreshTokenMiddleware
    only runs for a route explicitly marked via one of those decorators (see
    iam_core.user_auth.middleware.validate_and_refresh.dispatch — "Skip auth
    for unmarked routes"), so leaving this endpoint undecorated is what lets
    AWE call it without a staff browser session at all.

    Unlike the webhook controller, though, AWE's own "http" approver-rule
    caller (awe/services/resolver.py::_resolve_http) sends a plain, unsigned
    POST — there is no signature header to verify here the way the webhook
    controller does. A shared secret baked into the URL's own query string
    (set once, in the approval_stage seed SQL's rule_value.url, never sent
    by staff-ui or any browser) is the only protection available for this
    endpoint shape — checked against the APPROVER_RESOLVER_SECRET env var.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.router.tags += ["/livestock/approver-resolver"]
        # ONE fixed path (level comes from a query param, not the path) so
        # the CSRF exemption this endpoint needs (see
        # docker/staff-api/core-patches/apply_patches.py Fix 6, which adds
        # this exact path to openg2p_registry_staff_api/main.py's
        # REGISTRY_STAFF_CSRF_EXCLUDED_PATHS) only has to name one string —
        # CsrfMiddleware's _path_is_excluded does plain suffix matching, not
        # a wildcard/prefix match, so a per-level path segment would have
        # needed 4 separate excluded-path entries kept in lockstep instead.
        self.router.add_api_route("/livestock/approver-resolver", self.resolve, methods=["POST"])

    async def resolve(self, request: Request) -> JSONResponse:
        level = request.query_params.get("level") or ""
        expected = (os.environ.get("APPROVER_RESOLVER_SECRET") or "").strip()
        provided = request.query_params.get("secret") or ""
        if not expected or provided != expected:
            _logger.warning("approver-resolver: rejected call for level=%s (bad/missing secret)", level)
            return JSONResponse({"user_ids": []}, status_code=401)

        try:
            body = await request.json()
        except Exception:
            body = {}
        context = (body or {}).get("context") or {}
        location_value = context.get(level)
        if not location_value:
            # Blank location at this level -> every holder of the level's role
            # (Gen1 parity, see resolve_approvers); never "nobody".
            _logger.info("approver-resolver: no '%s' value in context, resolving to all %s approvers", level, level)

        user_ids = await resolve_approvers(level, str(location_value) if location_value else None)
        _logger.info(
            "approver-resolver: level=%s location=%r -> %s", level, location_value, user_ids
        )
        return JSONResponse({"user_ids": user_ids})
