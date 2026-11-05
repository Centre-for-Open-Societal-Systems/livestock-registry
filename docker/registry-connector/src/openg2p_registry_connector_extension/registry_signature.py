"""Detached JWS over the envelope's message payload, as the registry partner API verifies it.

The key belongs to the connector's sender partner (g2p_sender_id). Sources, in order:

1. the connector's write-only auth secrets, ``auth_secret_json.registry_signature``:
   ``{"key_pem": ..., "key_id": ..., "algorithm": "EdDSA"}`` (set through the admin API);
2. ``CONNECTOR_REGISTRY_SIGNATURE_KEY_PEM`` / ``_KEY_ID`` / ``_ALGORITHM``;
3. ``CONNECTOR_SIGNING_KEY_PEM`` / ``CONNECTOR_SIGNING_KID``, the variables the Helm release of
   the connector renders into the api, worker and beat containers (algorithm EdDSA unless
   ``CONNECTOR_SIGNING_ALGORITHM`` says otherwise). The earlier connector image signed with
   these, and nothing else on New Dev sets a key, so they must keep working.

The connector API never returns auth secrets. The first source that holds a key is used
whole, and it is logged once per process (never the key).
"""

import json
import logging
import os
from typing import Any

from jwt.api_jws import PyJWS

_logger = logging.getLogger("connector.extension.registry_signature")
_logged_sources: set[str] = set()

KEY_ENV = "CONNECTOR_REGISTRY_SIGNATURE_KEY_PEM"
KEY_ID_ENV = "CONNECTOR_REGISTRY_SIGNATURE_KEY_ID"
ALGORITHM_ENV = "CONNECTOR_REGISTRY_SIGNATURE_ALGORITHM"
HELM_KEY_ENV = "CONNECTOR_SIGNING_KEY_PEM"
HELM_KEY_ID_ENV = "CONNECTOR_SIGNING_KID"
HELM_ALGORITHM_ENV = "CONNECTOR_SIGNING_ALGORITHM"
ALGORITHMS = ("EdDSA", "ES256", "RS256")


def canonical_payload(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _pem(value: str) -> str:
    """A PEM passed through an environment file may carry literal backslash-n."""
    value = value or ""
    return value if "\n" in value.strip() else value.replace(chr(92) + "n", "\n")


def _sources(connector):
    stored = (connector.get_auth_secrets() or {}).get("registry_signature") or {}
    env = os.environ.get
    yield "auth_secret_json.registry_signature", stored.get("key_pem"), stored.get("key_id"), stored.get("algorithm")
    yield KEY_ENV, env(KEY_ENV), env(KEY_ID_ENV), env(ALGORITHM_ENV)
    yield HELM_KEY_ENV, env(HELM_KEY_ENV), env(HELM_KEY_ID_ENV), env(HELM_ALGORITHM_ENV)


def signing_key(connector) -> tuple[str, str, str]:
    for source, key, key_id, algorithm in _sources(connector):
        if not (key or "").strip():
            continue
        key, key_id, algorithm = _pem(key), (key_id or "").strip(), (algorithm or "EdDSA").strip()
        if not key_id:
            raise ValueError(f"Registry signature key from {source} has no key id")
        if algorithm not in ALGORITHMS:
            raise ValueError(f"Registry signature algorithm must be one of {', '.join(ALGORITHMS)}")
        if source not in _logged_sources:
            _logged_sources.add(source)
            _logger.info("Registry signature key source: %s (key id %s, algorithm %s)", source, key_id, algorithm)
        return key, key_id, algorithm
    raise ValueError("Registry signature is not configured (auth_secret_json.registry_signature)")


def sign_envelope(connector, envelope: dict[str, Any]) -> dict[str, Any]:
    key, key_id, algorithm = signing_key(connector)
    try:
        token = PyJWS().encode(canonical_payload(envelope["message"]["payload"]), key,
                               algorithm=algorithm, headers={"kid": key_id})
    except Exception:
        raise ValueError("Registry signature failed") from None
    protected, _, signature = token.split(".")
    envelope["header"].update(signature=f"{protected}..{signature}", signature_algorithm=algorithm)
    return envelope
