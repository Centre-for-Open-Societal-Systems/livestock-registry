"""Read the geo-hierarchy widget's document into the per-level id columns.

The Location sections bind the native geo-hierarchy widget to the register's
geo_lowest_level_value_id / geo_code_hierarchy_json (Master Data geo unit ids,
P-codes: ET04, ET0404, ET040404, ET040404888003). The document is
``{"hierarchy": [{"level_id": "l1", "level_mnemonic": "region",
"level_value_id": "ET04", "level_value_mnemonic": "Oromia"}, ...],
"lowest_level_value_id": ...}``; region_id ... kebele_id are filled from it so
approver routing, alerts, reminders and reports keep reading one column per
level. No Master Data call happens here; the names come from the document and
are refreshed from Master Data by admin_area_sync.
"""

import json

LEVELS = ("region", "zone", "woreda", "kebele")


def hierarchy_entries(document) -> list[dict]:
    """The level entries of a hierarchy document (dict or JSON text), [] when
    there is none or it is not a document."""
    if isinstance(document, str):
        try:
            document = json.loads(document)
        except ValueError:
            return []
    if isinstance(document, list):
        entries = document
    elif isinstance(document, dict):
        entries = document.get("hierarchy")
    else:
        return []
    return [entry for entry in entries or [] if isinstance(entry, dict)]


def hierarchy_places(document) -> dict[str, tuple[str, str | None]]:
    """``{level: (geo unit id, name or None)}`` for the administrative levels
    present in the document."""
    places: dict[str, tuple[str, str | None]] = {}
    for entry in hierarchy_entries(document):
        level = str(entry.get("level_mnemonic") or entry.get("level") or "").strip().lower()
        value_id = entry.get("level_value_id")
        if level in LEVELS and value_id not in (None, ""):
            label = entry.get("level_value_mnemonic") or entry.get("display_name") or None
            places[level] = (str(value_id), str(label) if label else None)
    return places


def apply_hierarchy(row) -> bool:
    """Set ``<level>_id`` (and a missing name) on ``row`` from its
    geo_code_hierarchy_json. A level the document does not reach is cleared,
    so choosing a woreda after a kebele leaves no stale kebele behind. True if
    anything changed; False when the row has no document."""
    places = hierarchy_places(getattr(row, "geo_code_hierarchy_json", None))
    if not places:
        return False
    changed = False
    for level in LEVELS:
        value_id, label = places.get(level, (None, None))
        if getattr(row, f"{level}_id", None) != value_id:
            setattr(row, f"{level}_id", value_id)
            changed = True
        if label and not getattr(row, level, None):
            setattr(row, level, label)
            changed = True
    return changed
