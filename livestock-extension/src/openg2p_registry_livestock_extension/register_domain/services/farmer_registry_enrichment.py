"""Farmer Registry enrichment for the Farmer section of the web intake form.

The Farmer Registry is the system of record for people (see G2PFarmer's module
docstring), so once the operator has entered a Farmer ID the registry's own
copy of that farmer's identity replaces whatever was typed. Three steps:

1. fetch_farmer_record: a DCI `idtype-value` search on the Farmer Registry's
   partner API (POST {FARMER_REGISTRY_DCI_SEARCH_URL}). The registry is a
   consent-enforcing PEP, so every call carries two RS256/EdDSA/ES256
   signatures made with this registry's partner key, as registered in Partner
   Management:
     * `signature`: a detached JWS over the canonical {header, message} JSON —
       sorted keys, no whitespace, exactly what the registry re-serialises
       with orjson OPT_SORT_KEYS before verifying. The registry looks the key
       up under "PARTNER_<header.sender_id>", so the sender id is the partner
       id WITHOUT its PARTNER_ prefix (LIVESTOCK_TEST, not
       PARTNER_LIVESTOCK_TEST).
     * `search_criteria.authorize.consent_jws`: a compact JWS over a consent
       object, which the registry forwards verbatim to the Consent Manager.
       The CM finds the partner by the consent's `aud`, rejects a reused `jti`
       and an `issued_at` outside its freshness window (300s by default), and
       evaluates the partner's policy — so a new one is signed per call.
2. to_farmer_fields: reduce the raw `farmer_personal_details` record to the
   plain Farmer register fields (first/middle/last name, gender,
   date_of_birth, mobile_number). Nothing else from the response is kept,
   and the raw response itself is not stored.
3. The caller (G2PRegisterDomainServiceFarmer.pre_finalize, on submit) writes
   those fields onto the still-draft intake row before it goes to approval,
   so the clean data is what approvers see and what reaches the register.

Fails open: when enrichment is switched off or misconfigured, the registry is
unreachable, rejects the call, or does not find exactly one farmer, this logs
a warning and returns None, and the operator's own entries stand. Intake is
never blocked on the Farmer Registry.
"""

import logging
import os
import uuid
from datetime import date, datetime, timedelta, timezone

import httpx
import jwt
import orjson

from .domain_validation_utils import is_blank, parse_date

_logger = logging.getLogger("g2p-farmer-registry-enrichment")

# The DCI response's `sex` (male/female/others/unknown, see the Farmer
# Registry's openg2p_farmer_to_dci.json.j2 sex() macro) -> the GENDER values
# this registry's Farmer rows carry. Anything else is left unset.
_SEX_TO_GENDER = {"male": "MALE", "female": "FEMALE"}


def _setting(name: str, default: str = "") -> str:
    return (os.environ.get(f"FARMER_REGISTRY_{name}") or default).strip()


def _config() -> dict | None:
    """Enrichment settings from FARMER_REGISTRY_* on staff-api. None, after a
    warning, when enrichment is off or a required setting is missing."""
    if _setting("ENRICHMENT_ENABLED", "false").lower() not in {"true", "1", "yes"}:
        return None

    signing_key = _setting("SIGNING_KEY")
    key_path = _setting("SIGNING_KEY_PATH")
    if not signing_key and key_path:
        try:
            with open(key_path, encoding="utf-8") as key_file:
                signing_key = key_file.read()
        except OSError as exc:
            _logger.warning("Farmer Registry enrichment: cannot read signing key %s: %s", key_path, exc)
            return None

    # Parse the timeout defensively: a bad value like "10s" would otherwise raise
    # ValueError out of _config and escape into Submit. Skip enrichment instead.
    raw_timeout = _setting("TIMEOUT_SECONDS", "10") or "10"
    try:
        timeout = float(raw_timeout)
    except (TypeError, ValueError):
        timeout = 0.0
    if not (timeout > 0 and timeout != float("inf")):
        _logger.warning(
            "Farmer Registry enrichment: invalid FARMER_REGISTRY_TIMEOUT_SECONDS %r — skipping",
            raw_timeout,
        )
        return None

    cfg = {
        "search_url": _setting("DCI_SEARCH_URL"),
        "sender_id": _setting("SENDER_ID"),
        "receiver_id": _setting("RECEIVER_ID", "farmer-registry"),
        "signing_key": signing_key,
        "kid": _setting("SIGNING_KEY_KID"),
        "algorithm": _setting("SIGNING_ALGORITHM", "RS256"),
        "consent_audience": _setting("CONSENT_AUDIENCE"),
        "consent_data_controller": _setting("CONSENT_DATA_CONTROLLER", "farmer-registry"),
        "consent_scopes": [s.strip() for s in _setting("CONSENT_SCOPES", "farmer_personal_details").split(",") if s.strip()],
        "consent_purpose": _setting("CONSENT_PURPOSE"),
        "timeout": timeout,
    }
    missing = [
        name
        for name in ("search_url", "sender_id", "signing_key", "kid", "consent_audience", "consent_purpose")
        if not cfg[name]
    ]
    if missing:
        _logger.warning(
            "Farmer Registry enrichment is enabled but not configured (missing %s) — skipping",
            ", ".join(missing),
        )
        return None
    return cfg


def _sign(payload: bytes, cfg: dict, *, detached: bool) -> str:
    token = jwt.api_jws.PyJWS().encode(
        payload,
        cfg["signing_key"],
        algorithm=cfg["algorithm"],
        headers={"kid": cfg["kid"]},
    )
    if not detached:
        return token
    # Detached by dropping the payload segment only. Not PyJWT's
    # is_payload_detached: that switches to RFC 7797's unencoded payload
    # (b64=false), while the registry verifies over the base64url-encoded
    # payload, as an ordinary JWS signs it.
    protected, _, signature = token.split(".")
    return f"{protected}..{signature}"


def _consent_jws(farmer_id: str, now: datetime, cfg: dict) -> str:
    issued_at = now.isoformat()
    consent = {
        "@context": "https://openg2p.org/contexts/consent_object.jsonld",
        "@type": "ConsentObject",
        "jti": uuid.uuid4().hex,
        "aud": cfg["consent_audience"],
        "data_controller": cfg["consent_data_controller"],
        "data_scopes": cfg["consent_scopes"],
        "fetch_type": "oneshot",
        "issued_at": issued_at,
        "purpose": {"code": cfg["consent_purpose"], "text": "Livestock registry intake: farmer enrichment"},
        "subject_id": {"type": "farmer_id", "value": farmer_id},
        "validity": {"valid_from": issued_at, "valid_until": (now + timedelta(hours=1)).isoformat()},
    }
    return _sign(orjson.dumps(consent), cfg, detached=False)


def build_search_request(farmer_id: str, cfg: dict) -> dict:
    """The signed DCI search envelope for one Farmer ID."""
    now = datetime.now(timezone.utc)
    timestamp = now.isoformat()
    header = {
        "version": "1.0.0",
        "message_id": uuid.uuid4().hex,
        "message_ts": timestamp,
        "action": "search",
        "sender_id": cfg["sender_id"],
        "receiver_id": cfg["receiver_id"],
        "total_count": 1,
        "is_msg_encrypted": False,
    }
    message = {
        "transaction_id": uuid.uuid4().hex[:12],
        "search_request": [
            {
                "reference_id": uuid.uuid4().hex,
                "timestamp": timestamp,
                "locale": "eng",
                "search_criteria": {
                    "version": "1.0.0",
                    "reg_type": "Farmer",
                    "reg_record_type": "spdci-extensions-dci:FarmerRecord",
                    "query_type": "idtype-value",
                    "query": {
                        "type": "idtype-value",
                        "value": {"id_type": "functional_id", "id_value": farmer_id},
                    },
                    "pagination": {"page_size": 10, "page_number": 1},
                    "authorize": {"consent_jws": _consent_jws(farmer_id, now, cfg)},
                },
            }
        ],
    }
    # Signed last: any change to header/message after this breaks it.
    canonical = orjson.dumps({"header": header, "message": message}, option=orjson.OPT_SORT_KEYS)
    return {"signature": _sign(canonical, cfg, detached=True), "header": header, "message": message}


async def fetch_farmer_record(farmer_id: str) -> dict | None:
    """The Farmer Registry's `farmer_personal_details` for this Farmer ID, or
    None when enrichment is off/misconfigured, the call fails or is rejected,
    or the search does not return exactly one farmer.

    Exactly one, because the registry's idtype-value search is a full-text
    search over its search_text column (id_type is not used to pick a
    column), and the record it returns carries the farmer's foundational id,
    not the Farmer ID — so the match cannot be confirmed from the record
    itself, and an ambiguous result is safer ignored than applied."""
    if is_blank(farmer_id):
        return None

    # Config parse, the HTTP call, AND response-shape parsing are all inside the
    # fail-open guard: a bad setting, a non-dict envelope (e.g. an upstream "[]"),
    # or a missing nested field must never escape into Submit — they log and skip.
    try:
        cfg = _config()
        if cfg is None:
            return None
        farmer_id = str(farmer_id).strip().upper()

        request_body = build_search_request(farmer_id, cfg)
        async with httpx.AsyncClient(timeout=cfg["timeout"]) as client:
            response = await client.post(cfg["search_url"], json=request_body)
        response.raise_for_status()
        envelope = response.json()

        if not isinstance(envelope, dict):
            _logger.warning("Farmer Registry lookup for %s: unexpected response shape %s — not enriching", farmer_id, type(envelope).__name__)
            return None

        header = envelope.get("header")
        header = header if isinstance(header, dict) else {}
        if header.get("status") != "succ":
            _logger.warning(
                "Farmer Registry rejected the lookup for %s: %s %s",
                farmer_id, header.get("status_reason_code"), header.get("status_reason_message"),
            )
            return None

        message = envelope.get("message")
        message = message if isinstance(message, dict) else {}
        items = message.get("search_response")
        items = items if isinstance(items, list) else []
        item = items[0] if items and isinstance(items[0], dict) else {}
        data = item.get("data")
        data = data if isinstance(data, dict) else {}
        records = data.get("reg_records")
        records = records if isinstance(records, list) else []
        pagination = item.get("pagination")
        pagination = pagination if isinstance(pagination, dict) else {}
        total = pagination.get("total_count")
        if item.get("status") != "succ" or len(records) != 1 or total not in (None, 1):
            _logger.warning(
                "Farmer Registry lookup for %s returned %s record(s) (status=%s) — not enriching",
                farmer_id, total if total is not None else len(records), item.get("status"),
            )
            return None

        record0 = records[0] if isinstance(records[0], dict) else {}
        personal = record0.get("farmer_personal_details")
        if not isinstance(personal, dict) or not personal:
            # Present but clamped to nothing: the consent's effective scopes do
            # not include farmer_personal_details (Consent Manager policy).
            _logger.warning(
                "Farmer Registry returned no farmer_personal_details for %s — check the consent scopes",
                farmer_id,
            )
            return None
        return personal
    except Exception as exc:
        # repr, not str: httpx timeouts stringify to "".
        _logger.warning("Farmer Registry lookup for %s failed: %r", farmer_id, exc)
        return None


def _text(value) -> str | None:
    return None if is_blank(value) else str(value).strip()


def to_farmer_fields(personal: dict) -> dict:
    """The plain Farmer register fields carried by a DCI
    `farmer_personal_details` record. Name parts are always returned together
    (a blank one as None) so the registry's full name replaces the typed one;
    gender, date_of_birth and mobile_number only when the registry has a
    usable value."""
    fields: dict = {}
    if not isinstance(personal, dict):
        return fields
    demographic = personal.get("demographic_info")
    demographic = demographic if isinstance(demographic, dict) else {}
    name = demographic.get("name")
    name = name if isinstance(name, dict) else {}

    if not is_blank(name.get("given_name")) or not is_blank(name.get("surname")):
        fields["first_name"] = _text(name.get("given_name"))
        fields["middle_name"] = _text(name.get("second_name"))
        fields["last_name"] = _text(name.get("surname"))

    gender = _SEX_TO_GENDER.get(str(demographic.get("sex") or "").strip().lower())
    if gender:
        fields["gender"] = gender

    birth_date = parse_date(demographic.get("birth_date"))
    if birth_date and birth_date <= date.today():
        fields["date_of_birth"] = birth_date

    phones = demographic.get("phone_number") or []
    if isinstance(phones, str):
        phones = [phones]
    phone = next((_text(p) for p in phones if not is_blank(p)), None)
    if phone:
        fields["mobile_number"] = phone

    return fields
