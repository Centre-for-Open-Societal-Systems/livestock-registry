"""Enhanced Approver Resolver Service with Geo-Code Resolution & Multi-Tier Fallback.

Provides defensive location matching for the OpenG2P Livestock Registry hierarchical
approval chain (Kebele -> Woreda -> Zone -> Region):
1. Resolves administrative codes (e.g. numeric "30405401001") to human mnemonics ("Hara")
   via master_data.g2p_geo_level_values so matching succeeds regardless of whether
   submissions store raw codes or labels.
2. Performs case-insensitive, whitespace-tolerant matching against Keycloak user attributes
   (approver_location_value) and supports "*" wildcard approvers.
3. Multi-tier fallback hierarchy:
   - Tier 1: Level-specific approvers matching the location or wildcard "*".
   - Tier 2: Any approvers holding the level's role (unscoped fallback).
   - Tier 3: General platform approvers (Intake Validator, Operations Administrator, admin).
   This prevents AWE workflows from freezing with zero tasks (on_empty='block').
"""

import logging
import os
import sys
from typing import Any

import httpx

_logger = logging.getLogger("g2p-geo-approver-resolver")

_LEVEL_TO_ROLE = {
    "kebele": "Kebele Approver",
    "woreda": "Woreda Approver",
    "zone": "Zone Approver",
    "region": "Region Approver",
}

_LOCATION_ATTR = "approver_location_value"
_ALL_LOCATIONS = "*"

_master_data_engine = None
_GEO_CACHE: dict[str, str] = {}


def _get_md_engine():
    global _master_data_engine
    if _master_data_engine is not None:
        return _master_data_engine

    try:
        from sqlalchemy.ext.asyncio import create_async_engine
        md_host = (
            os.environ.get("REGISTRY_STAFF_PORTAL_API_MASTER_DATA_DB_HOSTNAME")
            or os.environ.get("REGISTRY_CELERY_WORKERS_MASTER_DATA_DB_HOSTNAME")
            or os.environ.get("REGISTRY_PARTNER_API_MASTER_DATA_DB_HOSTNAME")
            or os.environ.get("REGISTRY_CELERY_BEAT_MASTER_DATA_DB_HOSTNAME")
            or os.environ.get("REGISTRY_CORE_MASTER_DATA_DB_HOSTNAME")
            or os.environ.get("MASTER_DATA_DB_HOSTNAME")
            or "postgres"
        )
        md_port = (
            os.environ.get("REGISTRY_STAFF_PORTAL_API_MASTER_DATA_DB_PORT")
            or os.environ.get("REGISTRY_CELERY_WORKERS_MASTER_DATA_DB_PORT")
            or os.environ.get("REGISTRY_PARTNER_API_MASTER_DATA_DB_PORT")
            or os.environ.get("REGISTRY_CELERY_BEAT_MASTER_DATA_DB_PORT")
            or os.environ.get("REGISTRY_CORE_MASTER_DATA_DB_PORT")
            or os.environ.get("MASTER_DATA_DB_PORT")
            or "5432"
        )
        md_name = (
            os.environ.get("REGISTRY_STAFF_PORTAL_API_MASTER_DATA_DB_DBNAME")
            or os.environ.get("REGISTRY_CELERY_WORKERS_MASTER_DATA_DB_DBNAME")
            or os.environ.get("REGISTRY_PARTNER_API_MASTER_DATA_DB_DBNAME")
            or os.environ.get("REGISTRY_CELERY_BEAT_MASTER_DATA_DB_DBNAME")
            or os.environ.get("REGISTRY_CORE_MASTER_DATA_DB_DBNAME")
            or os.environ.get("MASTER_DATA_DB")
            or "master_data"
        )
        md_user = (
            os.environ.get("REGISTRY_STAFF_PORTAL_API_MASTER_DATA_DB_USERNAME")
            or os.environ.get("REGISTRY_CELERY_WORKERS_MASTER_DATA_DB_USERNAME")
            or os.environ.get("REGISTRY_PARTNER_API_MASTER_DATA_DB_USERNAME")
            or os.environ.get("REGISTRY_CELERY_BEAT_MASTER_DATA_DB_USERNAME")
            or os.environ.get("REGISTRY_CORE_MASTER_DATA_DB_USERNAME")
            or os.environ.get("MASTER_DATA_DB_USER")
            or "master_data_user"
        )
        md_pass = (
            os.environ.get("REGISTRY_STAFF_PORTAL_API_MASTER_DATA_DB_PASSWORD")
            or os.environ.get("REGISTRY_CELERY_WORKERS_MASTER_DATA_DB_PASSWORD")
            or os.environ.get("REGISTRY_PARTNER_API_MASTER_DATA_DB_PASSWORD")
            or os.environ.get("REGISTRY_CELERY_BEAT_MASTER_DATA_DB_PASSWORD")
            or os.environ.get("REGISTRY_CORE_MASTER_DATA_DB_PASSWORD")
            or os.environ.get("MASTER_DATA_DB_PASSWORD")
            or "master_data_pass"
        )
        dsn = f"postgresql+asyncpg://{md_user}:{md_pass}@{md_host}:{md_port}/{md_name}"
        _master_data_engine = create_async_engine(dsn, pool_pre_ping=True, pool_recycle=1800)
    except Exception as e:
        _logger.warning("Geo Approver Resolver: Could not create master_data engine: %s", e)
    return _master_data_engine


async def _resolve_geo_candidates(raw_loc: str, level: str) -> list[str]:
    """Given a location string (code or name), return all viable match candidates."""
    candidates = [raw_loc]
    raw_str = raw_loc.strip()

    if raw_str in _GEO_CACHE:
        cached = _GEO_CACHE[raw_str]
        if cached not in candidates:
            candidates.append(cached)
        return candidates

    engine = _get_md_engine()
    if engine is None:
        return candidates

    try:
        from sqlalchemy.ext.asyncio import async_sessionmaker
        from sqlalchemy import text

        session_maker = async_sessionmaker(engine, expire_on_commit=False)
        async with session_maker() as session:
            q = text(
                "SELECT level_value_id, level_value_mnemonic FROM g2p_geo_level_values "
                "WHERE level_value_id = :loc "
                "OR level_value_id = :prefixed "
                "OR level_value_id ILIKE :like_loc "
                "OR level_value_mnemonic ILIKE :loc "
                "LIMIT 1"
            )
            res = await session.execute(
                q,
                {
                    "loc": raw_str,
                    "prefixed": f"{level}-{raw_str}",
                    "like_loc": f"%{raw_str}",
                },
            )
            row = res.fetchone()
            if row:
                vid, vname = row[0], row[1]
                if vname and vname not in candidates:
                    candidates.append(vname)
                    _GEO_CACHE[raw_str] = vname
                if vid and vid not in candidates:
                    candidates.append(vid)
    except Exception as e:
        _logger.warning("Geo Approver Resolver: Lookup error for '%s': %s", raw_str, e)

    return candidates


def _keycloak_config() -> dict[str, Any] | None:
    """Read Keycloak configuration dynamically from environment or core Settings."""
    base = os.environ.get("KEYCLOAK_BASE_URL", "").strip().rstrip("/")
    host = os.environ.get("KEYCLOAK_HOST", "").strip()
    if not base and host:
        base = f"http://{host}:{os.environ.get('KEYCLOAK_PORT', '8080').strip() or '8080'}"
    if base:
        realm = os.environ.get("KEYCLOAK_REALM", "staff").strip() or "staff"
        return {
            "base": base,
            "token_realm": realm,
            "users_realm": realm,
            "client_id": os.environ.get("AUTH_CLIENT_ID", "livestock-staff-portal"),
            "client_secret": os.environ.get("AUTH_CLIENT_SECRET", ""),
        }

    try:
        from openg2p_registry_core.config import Settings
        cfg = Settings.get_config(strict=False)
    except Exception as exc:
        _logger.warning("Geo Approver Resolver: registry settings unavailable: %s", exc)
        return None

    url = (getattr(cfg, "keycloak_admin_url", None) or "").rstrip("/")
    client_id = getattr(cfg, "keycloak_admin_client_id", None)
    client_secret = getattr(cfg, "keycloak_admin_client_secret", None)
    if not (url and client_id and client_secret):
        _logger.warning("Geo Approver Resolver: Keycloak admin credentials not configured in settings")
        return None

    return {
        "base": url,
        "token_realm": getattr(cfg, "keycloak_admin_realm", None) or "master",
        "users_realm": getattr(cfg, "keycloak_realm", None) or "staff",
        "client_id": client_id,
        "client_secret": client_secret,
    }


def _roles_client_id() -> str:
    explicit = os.environ.get("APPROVER_ROLES_CLIENT_ID") or os.environ.get("AUTH_CLIENT_ID")
    if explicit:
        return explicit
    try:
        from openg2p_registry_core.config import Settings
        configured = getattr(Settings.get_config(strict=False), "keycloak_client_id", None)
    except Exception:
        configured = None
    return configured or "livestock-staff-portal"


async def _admin_token(client: httpx.AsyncClient, cfg: dict[str, Any]) -> str:
    resp = await client.post(
        f"{cfg['base']}/realms/{cfg['token_realm']}/protocol/openid-connect/token",
        data={
            "grant_type": "client_credentials",
            "client_id": cfg["client_id"],
            "client_secret": cfg["client_secret"],
        },
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


async def resolve_approvers_enhanced(level: str, location_value: str | None) -> list[str]:
    """Enhanced approver resolver with geo code-to-name lookup and multi-tier fallback."""
    role_name = _LEVEL_TO_ROLE.get(level)
    if not role_name:
        _logger.warning("Geo Approver Resolver: Unrecognized approval level '%s'", level)
        return []

    cfg = _keycloak_config()
    if cfg is None:
        _logger.error("Geo Approver Resolver: Keycloak configuration unavailable, returning fallback ['admin']")
        return ["admin"]

    base = cfg["base"]
    realm = cfg["users_realm"]

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            token = await _admin_token(client, cfg)
        except Exception as exc:
            _logger.warning("Geo Approver Resolver: could not get Keycloak admin token: %s", exc)
            return ["admin"]

        headers = {"Authorization": f"Bearer {token}"}

        # 1. Resolve client UUID for portal roles
        try:
            client_lookup = await client.get(
                f"{base}/admin/realms/{realm}/clients",
                headers=headers,
                params={"clientId": _roles_client_id()},
            )
            client_lookup.raise_for_status()
            found = client_lookup.json()
            if not found:
                _logger.warning("Geo Approver Resolver: Client '%s' not found in realm '%s'", _roles_client_id(), realm)
                return ["admin"]
            client_uuid = found[0]["id"]
        except Exception as exc:
            _logger.warning("Geo Approver Resolver: Client lookup error: %s", exc)
            return ["admin"]

        # 2. Get users holding the level role
        try:
            role_users_resp = await client.get(
                f"{base}/admin/realms/{realm}/clients/{client_uuid}/roles/{role_name}/users",
                headers=headers,
                params={"max": 200},
            )
            candidates = role_users_resp.json() if role_users_resp.status_code == 200 else []
        except Exception as exc:
            _logger.warning("Geo Approver Resolver: Role users lookup error for '%s': %s", role_name, exc)
            candidates = []

        raw_loc = (location_value or "").strip()
        candidate_locations = await _resolve_geo_candidates(raw_loc, level) if raw_loc else []

        matched: list[str] = []
        for candidate in candidates:
            username = candidate.get("username")
            if not username:
                continue

            if not raw_loc:
                # Unscoped record: any holder of the role may approve
                matched.append(username)
                continue

            # Fetch user details to inspect approver_location_value attribute
            try:
                user_resp = await client.get(
                    f"{base}/admin/realms/{realm}/users/{candidate['id']}",
                    headers=headers,
                )
                if user_resp.status_code != 200:
                    continue
                attrs = user_resp.json().get("attributes") or {}
                attr_values = attrs.get(_LOCATION_ATTR) or []
            except Exception:
                continue

            # Check wildcard "*"
            if _ALL_LOCATIONS in attr_values:
                matched.append(username)
                continue

            # Check exact match across candidate locations (code or mnemonic)
            if any(cand in attr_values for cand in candidate_locations):
                matched.append(username)
            else:
                # Case-insensitive / whitespace-tolerant comparison
                attr_values_norm = {str(v).strip().lower() for v in attr_values}
                if any(str(cand).strip().lower() in attr_values_norm for cand in candidate_locations):
                    matched.append(username)

        if matched:
            print(f"Geo Approver Resolver: level={level} location={raw_loc!r} candidates={candidate_locations!r} -> matched {matched}", flush=True)
            _logger.info(
                "Geo Approver Resolver: level=%s location=%r candidates=%r -> matched %s",
                level, raw_loc, candidate_locations, matched
            )
            return matched

        # Tier 1 Fallback: Holders of this level's role exist, but none matched location
        level_usernames = [c.get("username") for c in candidates if c.get("username")]
        if level_usernames:
            print(f"Geo Approver Resolver: Fallback to level role holders: {level_usernames}", flush=True)
            _logger.warning(
                "Geo Approver Resolver: No exact match for level=%s location=%r (candidates=%r). "
                "Falling back to all level role holders: %s",
                level, raw_loc, candidate_locations, level_usernames
            )
            return level_usernames

        # Tier 2 Fallback: General platform approvers
        for fallback_role in ("Intake Validator", "Operations Administrator", "Technical Administrator"):
            try:
                fb_resp = await client.get(
                    f"{base}/admin/realms/{realm}/clients/{client_uuid}/roles/{fallback_role}/users",
                    headers=headers,
                    params={"max": 50},
                )
                if fb_resp.status_code == 200:
                    fb_users = [u.get("username") for u in fb_resp.json() if u.get("username")]
                    if fb_users:
                        print(f"Geo Approver Resolver: Fallback to {fallback_role}: {fb_users}", flush=True)
                        _logger.warning(
                            "Geo Approver Resolver: Falling back to platform role '%s': %s",
                            fallback_role, fb_users
                        )
                        return fb_users
            except Exception:
                pass

        # Tier 3 Fallback: 'admin' user
        print("Geo Approver Resolver: Fallback to admin", flush=True)
        _logger.warning("Geo Approver Resolver: No approvers found at any tier, falling back to ['admin']")
        return ["admin"]


def install_geo_approver_resolver():
    """Dynamically installs enhanced resolver into the existing service and controller without modifying their source code."""
    try:
        from . import approver_resolver_service
        approver_resolver_service.resolve_approvers = resolve_approvers_enhanced
        _logger.info("Geo Approver Resolver: Successfully installed into approver_resolver_service")
    except Exception as e:
        _logger.warning("Geo Approver Resolver: Could not patch approver_resolver_service: %s", e)

    try:
        from ..controllers import g2p_approver_resolver_controller
        g2p_approver_resolver_controller.resolve_approvers = resolve_approvers_enhanced
        _logger.info("Geo Approver Resolver: Successfully installed into g2p_approver_resolver_controller")
    except Exception as e:
        _logger.warning("Geo Approver Resolver: Could not patch g2p_approver_resolver_controller: %s", e)

    # Ensure /livestock/approver-resolver router is mounted on the active FastAPI application
    try:
        from openg2p_fastapi_common.context import app_registry

        def _ensure_resolver_route(app):
            if app and not any(getattr(r, "path", None) == "/livestock/approver-resolver" for r in getattr(app, "routes", [])):
                from ..controllers.g2p_approver_resolver_controller import G2PApproverResolverController
                ctrl = G2PApproverResolverController()
                app.include_router(ctrl.router)
                print("Geo Approver Resolver: Successfully registered /livestock/approver-resolver route onto FastAPI app", flush=True)

        orig_set = getattr(app_registry, "set", None)
        if orig_set:
            def _patched_set(value):
                orig_set(value)
                _ensure_resolver_route(value)

            app_registry.set = _patched_set

        cur_app = app_registry.get()
        if cur_app:
            _ensure_resolver_route(cur_app)
    except Exception as e:
        print(f"Geo Approver Resolver: Error ensuring route registration: {e}", flush=True)


# Auto-install on module import
install_geo_approver_resolver()
