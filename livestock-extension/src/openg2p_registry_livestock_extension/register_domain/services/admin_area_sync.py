"""Keep a record's admin area names and Master Data ids in step.

The Location sections use the native geo-hierarchy widget, which writes the
register's geo_lowest_level_value_id and geo_code_hierarchy_json (Master Data
geo unit ids, P-codes). geo_hierarchy.apply_hierarchy copies the chain into
region_id / zone_id / woreda_id / kebele_id first; everything else (approver
routing, outbreak alerts, reminders, reports, ODK) reads the names in region /
zone / woreda / kebele. sync_admin_area then fills one side from the other:

- a row that carries ids (portal entry, ODK v5 forms): the names follow the ids,
  and a level without an id loses its name (choosing another region clears the
  zone below it);
- a row that carries only the chosen place (geo_lowest_level_value_id, as the
  holding map writes it, or a widget save that left the document empty): the
  chain above it is read from Master Data and handled as ids; a code Master
  Data does not know changes nothing;
- a row with names only (older ODK forms, File Import, records saved before the
  ids existed): each id is looked up from its name under its parent, and the
  names stay as given, even for a place Master Data does not know.
"""

from ...master_data_lists import geo_chain, geo_id_for, geo_label
from .geo_hierarchy import apply_hierarchy

LEVELS = ("region", "zone", "woreda", "kebele")


async def sync_admin_area(row) -> bool:
    """Fill the names from the ids, or the ids from the names. True if changed."""
    if not all(hasattr(row, level) and hasattr(row, f"{level}_id") for level in LEVELS):
        return False
    changed = await _hierarchy_from_lowest_value(row)
    changed = apply_hierarchy(row) or changed
    from_ids = any(getattr(row, f"{level}_id", None) for level in LEVELS)
    parent_id = parent_name = None
    for level in LEVELS:
        value_id = getattr(row, f"{level}_id", None)
        name = getattr(row, level, None)
        if from_ids:
            label = await geo_label(value_id) if value_id else None
            new_name = label or (name if value_id else None)
            if new_name != name:
                setattr(row, level, new_name)
                name, changed = new_name, True
        elif name:
            found = await geo_id_for(level, name, parent_id, parent_name)
            if found:
                setattr(row, f"{level}_id", found)
                value_id, changed = found, True
        parent_id, parent_name = value_id, name
    return changed


async def _hierarchy_from_lowest_value(row) -> bool:
    """Write the hierarchy document from geo_lowest_level_value_id when the row
    has a chosen place but no document and no level ids. True if written."""
    lowest = getattr(row, "geo_lowest_level_value_id", None)
    if not lowest or getattr(row, "geo_code_hierarchy_json", None):
        return False
    if any(getattr(row, f"{level}_id", None) for level in LEVELS):
        return False
    chain = await geo_chain(lowest)
    if not any(entry.get("level_mnemonic") in LEVELS for entry in chain):
        return False
    row.geo_code_hierarchy_json = {
        "hierarchy": chain,
        "lowest_level_value_id": str(lowest).strip(),
    }
    return True
