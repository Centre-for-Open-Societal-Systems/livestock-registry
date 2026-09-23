__version__ = "1.0.0"
__variant__ = "livestock"

import os

# Bridge staff-api / platform settings to iam_core common_ settings
_redis_url = os.environ.get("REGISTRY_STAFF_PORTAL_API_AUTH_REDIS_URL") or os.environ.get("COMMON_AUTH_REDIS_URL")
if _redis_url:
    os.environ["COMMON_AUTH_REDIS_URL"] = _redis_url

_auth_provider_url = os.environ.get("REGISTRY_STAFF_PORTAL_API_AUTH_PROVIDER_API_URL") or os.environ.get("COMMON_AUTH_PROVIDER_API_URL")
if _auth_provider_url:
    os.environ["COMMON_AUTH_PROVIDER_API_URL"] = _auth_provider_url

_client_id = os.environ.get("REGISTRY_STAFF_PORTAL_API_KEYCLOAK_CLIENT_ID") or os.environ.get("COMMON_KEYCLOAK_CLIENT_ID")
if _client_id:
    os.environ["COMMON_KEYCLOAK_CLIENT_ID"] = _client_id

try:
    from iam_core.user_auth.config import Settings as IamSettings
    _iam_cfg = IamSettings.get_config(strict=False)
    if _redis_url:
        _iam_cfg.auth_redis_url = _redis_url
    if _auth_provider_url:
        _iam_cfg.auth_provider_api_url = _auth_provider_url
    if _client_id:
        _iam_cfg.keycloak_client_id = _client_id
except Exception:
    pass

try:
    from . import odk_ingest_hooks  # noqa: F401
except Exception:
    pass
