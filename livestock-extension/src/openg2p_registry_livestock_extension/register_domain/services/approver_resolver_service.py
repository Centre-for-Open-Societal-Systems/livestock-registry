"""Keycloak lookup backing the approver-resolver HTTP endpoint (see
`g2p_approver_resolver_controller.py`): given a hierarchical approval level
(kebele/woreda/zone/region) and the specific location value the record being
approved carries at that level, return the username(s) of whichever staff
user holds BOTH the matching client role (Kebele/Woreda/Zone/Region
Approver, under `livestock-staff-portal`) AND an `approver_location_value`
attribute equal to that same location string.

This is the piece that makes the approval chain actually per-location, not
just per-role: AWE's own built-in `rule_type: "role"` resolver
(awe/services/resolver.py::_resolve_keycloak_role) returns EVERY holder of a
role platform-wide, which is exactly the "any Woreda Approver can approve
any woreda's record" behavior the real Ethiopian workflow does not want —
see [[livestock-4-level-approval-chain]] plan. Mirrors that same resolver's
two-step client-role lookup (client id -> uuid -> role's users), just with
an extra attribute filter applied after.
"""

import logging
import os

import httpx

_logger = logging.getLogger("g2p-approver-resolver")

_LEVEL_TO_ROLE = {
    "kebele": "Kebele Approver",
    "woreda": "Woreda Approver",
    "zone": "Zone Approver",
    "region": "Region Approver",
}

_LOCATION_ATTR = "approver_location_value"


def _keycloak_base_url() -> str:
    host = os.environ.get("KEYCLOAK_HOST", "keycloak")
    port = os.environ.get("KEYCLOAK_PORT", "8080")
    return f"http://{host}:{port}"


def _keycloak_realm() -> str:
    return os.environ.get("KEYCLOAK_REALM", "staff")


async def _admin_token(client: httpx.AsyncClient) -> str:
    """Client-credentials token for `livestock-staff-portal`'s own service
    account — granted view-users/query-users/view-clients/query-clients on
    realm-management in realm-staff.json specifically for this lookup (see
    that file's `service-account-livestock-staff-portal` entry)."""
    client_id = os.environ.get("AUTH_CLIENT_ID", "livestock-staff-portal")
    client_secret = os.environ.get("AUTH_CLIENT_SECRET", "")
    resp = await client.post(
        f"{_keycloak_base_url()}/realms/{_keycloak_realm()}/protocol/openid-connect/token",
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


async def resolve_approvers(level: str, location_value: str | None) -> list[str]:
    """Return the username(s) of the approver(s) for this level+location.
    Empty list (not an error) if the role, the client, or a matching user
    doesn't exist — the caller (the resolver controller) reports that back
    to AWE as `{"user_ids": []}`, which AWE's own `on_empty='block'` stage
    config then correctly stalls on, same as any other unresolved stage.

    A record with NO location at this level (blank kebele/woreda/zone/region)
    resolves to EVERY holder of the level's role — the Old System's rule
    (`livestock_record_rules.xml`: `'|', (kebele_id, '=', False),
    (kebele_id, '=', user.partner_id.kebele.id)`, and `_check_approver` only
    refusing when BOTH sides carry a location that differs). Without this,
    an unscoped record — every Gen1 holding whose farmer had no location,
    for one — resolves to nobody and AWE terminates it as rejected within a
    second, with no task for anyone and no reason shown."""
    role_name = _LEVEL_TO_ROLE.get(level)
    if not role_name:
        return []
    location_value = (location_value or "").strip() or None

    base = _keycloak_base_url()
    realm = _keycloak_realm()
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            token = await _admin_token(client)
        except httpx.HTTPError as exc:
            _logger.warning("approver-resolver: could not get Keycloak admin token: %s", exc)
            return []
        headers = {"Authorization": f"Bearer {token}"}

        client_lookup = await client.get(
            f"{base}/admin/realms/{realm}/clients",
            headers=headers,
            params={"clientId": "livestock-staff-portal"},
        )
        client_lookup.raise_for_status()
        found = client_lookup.json()
        if not found:
            return []
        client_uuid = found[0]["id"]

        role_users_resp = await client.get(
            f"{base}/admin/realms/{realm}/clients/{client_uuid}/roles/{role_name}/users",
            headers=headers,
            params={"max": 200},
        )
        if role_users_resp.status_code == 404:
            return []
        role_users_resp.raise_for_status()
        candidates = role_users_resp.json()

        matched: list[str] = []
        for candidate in candidates:
            username = candidate.get("username")
            if not username:
                continue
            if location_value is None:
                # Unscoped record: any holder of the role may approve (Gen1 rule).
                matched.append(username)
                continue
            # The role-members listing may not include attributes inline —
            # fetch the full user representation to check reliably.
            user_resp = await client.get(
                f"{base}/admin/realms/{realm}/users/{candidate['id']}",
                headers=headers,
            )
            if user_resp.status_code != 200:
                continue
            attrs = user_resp.json().get("attributes") or {}
            values = attrs.get(_LOCATION_ATTR) or []
            if location_value in values:
                matched.append(username)

        return matched
