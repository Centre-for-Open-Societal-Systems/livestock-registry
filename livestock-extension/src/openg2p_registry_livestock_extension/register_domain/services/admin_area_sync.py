"""Keep a record's admin area names and Master Data ids in step.

The portal's location dropdowns write the geo value ids (region_id, zone_id,
woreda_id, kebele_id): a shared Master Data links a zone to its region by id,
so the cascade only works on ids. Everything else (approver routing, outbreak
alerts, reminders, reports, ODK) reads the names in region / zone / woreda /
kebele. sync_admin_area fills one side from the other:

- a row that carries ids (portal entry): the names follow the ids, and a level
  whose dropdown is empty loses its name (choosing another region clears the
  zone below it);
- a row with names only (ODK, File Import, records saved before the ids
  existed): each id is looked up from its name under its parent, and the names
  stay as given, even for a place Master Data does not know.
"""

from ...master_data_lists import geo_id_for, geo_label

LEVELS = ("region", "zone", "woreda", "kebele")


async def sync_admin_area(row) -> bool:
    """Fill the names from the ids, or the ids from the names. True if changed."""
    if not all(hasattr(row, level) and hasattr(row, f"{level}_id") for level in LEVELS):
        return False
    changed = False
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
