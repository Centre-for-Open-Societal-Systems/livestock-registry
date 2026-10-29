"""The livestock code lists and geography, read from Master Data.

registry-platform 1.2 keeps no copy of a country's code lists: species, breed,
vaccine, disease and the like live in the Master Data service and the platform
reads them over HTTP (openg2p_registry_core.helpers.master_data.MasterDataClient,
settings ``registry_<app>_master_data_api_url`` / ``_token_url`` /
``_client_id`` / ``_client_secret``). The platform's own client only exposes
the set of codes per list, which is what its validator needs. The livestock
rules also need a value's label (for a message a user can act on), its parent
(a breed's or vaccine's species) and the values of one list (ODK
normalisation), so this module fetches every value once and serves those from
a cache with the platform's ``master_data_cache_seconds`` lifetime.

Every lookup degrades the way the old table lookups did: a Master Data that is
not configured or not reachable yields "unknown" (``None`` / the raw id), never
an exception out of a validation.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

_logger = logging.getLogger("livestock-master-data")

_ATTRIBUTE_PAGE_SIZE = 500
_ATTRIBUTE_MAX_PAGES = 50

_values_by_id: dict[str, dict[str, Any]] = {}
_values_by_attribute: dict[str, list[dict[str, Any]]] = {}
_values_expire_at = 0.0
_values_loaded = False


def _client():
    from openg2p_registry_core.helpers.master_data import MasterDataClient

    client = MasterDataClient.get_component()
    if client is None:
        client = MasterDataClient()
    return client


def _ttl(client) -> float:
    try:
        return float(client._cache_ttl(client._settings()))
    except Exception:
        return 300.0


def is_configured() -> bool:
    try:
        client = _client()
        return bool(client.is_configured(client._settings()))
    except Exception:
        return False


def invalidate() -> None:
    global _values_by_id, _values_by_attribute, _values_expire_at, _values_loaded
    _values_by_id = {}
    _values_by_attribute = {}
    _values_expire_at = 0.0
    _values_loaded = False
    _catalogue_lists.clear()


async def _load_values() -> None:
    """Fetch every attribute value once; served from the cache until the TTL."""
    global _values_by_id, _values_by_attribute, _values_expire_at, _values_loaded
    now = time.monotonic()
    if _values_loaded and now < _values_expire_at:
        return

    client = _client()
    if not client.is_configured(client._settings()):
        if not _values_loaded:
            _logger.warning("Master Data is not configured; code-list lookups return unknown")
        _values_loaded = True
        _values_expire_at = now + 30.0
        return

    by_id: dict[str, dict[str, Any]] = {}
    by_attribute: dict[str, list[dict[str, Any]]] = {}
    for page in range(1, _ATTRIBUTE_MAX_PAGES + 1):
        payload = await client._post(
            "/attributes/get_attribute_values",
            payload={"attribute_id": None},
            pagination={"current_page": page, "page_size": _ATTRIBUTE_PAGE_SIZE},
        )
        if isinstance(payload, dict):
            rows = payload.get("attribute_values") or []
        elif isinstance(payload, list):
            rows = payload
        else:
            rows = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            value_id = row.get("value_id")
            attribute_id = row.get("attribute_id")
            if not value_id or not attribute_id:
                continue
            entry = {
                "value_id": value_id,
                "attribute_id": attribute_id,
                "value_code": row.get("value_code"),
                "value_display": row.get("value_display"),
                "parent_value_id": row.get("parent_value_id") or None,
                "sort_order": row.get("sort_order"),
            }
            by_id[value_id] = entry
            by_attribute.setdefault(attribute_id, []).append(entry)
        if len(rows) < _ATTRIBUTE_PAGE_SIZE:
            break

    for rows in by_attribute.values():
        rows.sort(key=lambda r: (r.get("sort_order") is None, r.get("sort_order") or 0, r["value_id"]))

    _values_by_id = by_id
    _values_by_attribute = by_attribute
    _values_loaded = True
    ttl = _ttl(client)
    _values_expire_at = now + ttl if ttl > 0 else now + 300.0


async def get_value(value_id: str | None) -> Optional[dict[str, Any]]:
    if not value_id:
        return None
    try:
        await _load_values()
    except Exception as exc:
        _logger.warning("Master Data attribute values unavailable: %s", exc)
        return _values_by_id.get(str(value_id).strip())
    return _values_by_id.get(str(value_id).strip())


async def get_values(attribute_id: str) -> list[dict[str, Any]]:
    """All values of one list, in display order (empty when unknown)."""
    try:
        await _load_values()
    except Exception as exc:
        _logger.warning("Master Data attribute values unavailable: %s", exc)
    return list(_values_by_attribute.get(attribute_id, []))


async def display(value_id: str | None) -> str:
    """The label of a value id, or the id itself when it is not a known value."""
    entry = await get_value(value_id)
    if entry and entry.get("value_display"):
        return str(entry["value_display"])
    return str(value_id)


async def parent(value_id: str | None) -> Optional[str]:
    """parent_value_id of a value (a breed's species), None when unknown or none."""
    entry = await get_value(value_id)
    return (entry or {}).get("parent_value_id") or None


_catalogue_lists: dict[str, tuple[float, dict[str, dict[str, Any]]]] = {}


async def get_list(list_code: str) -> dict[str, dict[str, Any]] | None:
    """The ACTIVE values of the published version of one Master Data list,
    keyed by value_id, each with its ``attributes`` (the typed per-value data
    a country pack declares in the list's ``attribute_schema``, e.g. a
    species' ``requires_ear_tag``). Read from the catalogue API
    (``/catalogue/get_list_values``), which, unlike the legacy
    ``/attributes`` API above, returns those attributes. None when Master
    Data is not configured or not reachable."""
    now = time.monotonic()
    cached = _catalogue_lists.get(list_code)
    if cached and now < cached[0]:
        return cached[1]
    try:
        client = _client()
        if not client.is_configured(client._settings()):
            return None
        values: dict[str, dict[str, Any]] = {}
        for page in range(1, _ATTRIBUTE_MAX_PAGES + 1):
            payload = await client._post(
                "/catalogue/get_list_values",
                payload={"list_code": list_code},
                pagination={"current_page": page, "page_size": _ATTRIBUTE_PAGE_SIZE},
            )
            rows = (payload or {}).get("values") if isinstance(payload, dict) else payload
            rows = rows if isinstance(rows, list) else []
            for row in rows:
                if not isinstance(row, dict) or not row.get("value_id"):
                    continue
                if str(row.get("status") or "ACTIVE").upper() != "ACTIVE":
                    continue
                values[row["value_id"]] = {
                    "value_id": row["value_id"],
                    "value_code": row.get("value_code"),
                    "display": row.get("display"),
                    "parent_code": row.get("parent_code") or None,
                    "attributes": row.get("attributes") or {},
                }
            if len(rows) < _ATTRIBUTE_PAGE_SIZE:
                break
    except Exception as exc:
        _logger.warning("Master Data list %s unavailable: %s", list_code, exc)
        return cached[1] if cached else None
    ttl = _ttl(client)
    _catalogue_lists[list_code] = (now + (ttl if ttl > 0 else 300.0), values)
    return values


async def value_attributes(list_code: str, value_id: str | None) -> dict[str, Any]:
    """``attributes`` of one value of a Master Data list; empty when the value
    or the list is unknown."""
    if not value_id:
        return {}
    values = await get_list(list_code) or {}
    return dict((values.get(str(value_id).strip()) or {}).get("attributes") or {})


_geo_label_cache: dict[str, str] = {}


async def geo_label(level_value_id: str | None) -> Optional[str]:
    """The display name of a geo unit id (``ET01010101`` -> ``Adi Hageray``),
    None when Master Data does not know it."""
    if not level_value_id:
        return None
    key = str(level_value_id).strip()
    if key in _geo_label_cache:
        return _geo_label_cache[key]
    try:
        client = _client()
        index = await client._load_geo_index()
    except Exception as exc:
        _logger.warning("Master Data geo index unavailable: %s", exc)
        return None
    node = index.get(key) if index else None
    label = (node or {}).get("level_value_mnemonic") or None
    if label:
        _geo_label_cache[key] = label
    return label


async def geo_label_by_suffix(code: str) -> Optional[str]:
    """Last-resort match of a bare code against the end of every geo value id.
    Returns a name only when exactly one value ends with the code."""
    if not code:
        return None
    try:
        index = await _client()._load_geo_index()
    except Exception as exc:
        _logger.warning("Master Data geo index unavailable: %s", exc)
        return None
    suffix = str(code).strip().lower()
    matches = [n for vid, n in (index or {}).items() if str(vid).lower().endswith(suffix)]
    if len(matches) == 1:
        return matches[0].get("level_value_mnemonic") or None
    return None


async def geo_id_for(level: str, name: str | None, parent_id: str | None = None,
                     parent_name: str | None = None) -> Optional[str]:
    """The geo value id of ``name`` at ``level`` (region / zone / woreda /
    kebele), under the given parent when one is known; None unless exactly one
    value matches. A parent is matched by id or, for a Master Data whose
    values point at their parent by name, by that name."""
    if not name or not str(name).strip():
        return None
    try:
        index = await _client()._load_geo_index()
    except Exception as exc:
        _logger.warning("Master Data geo index unavailable: %s", exc)
        return None
    want = str(name).strip().casefold()
    matches = [
        vid for vid, node in (index or {}).items()
        if (node.get("level_mnemonic") or "").casefold() == level
        and (node.get("level_value_mnemonic") or "").strip().casefold() == want
    ]
    if len(matches) > 1 and (parent_id or parent_name):
        parents = {p for p in (parent_id, parent_name) if p}
        matches = [vid for vid in matches if index[vid].get("parent_level_value_id") in parents]
    return matches[0] if len(matches) == 1 else None
