-- Patch for already-seeded environments only.
--
-- g2p_register_sections.sql is a one-shot db-seed INSERT, so it only applies
-- on a fresh database. An environment that was seeded before ear_tag_id
-- became species-conditional needs this UPDATE instead, to patch the
-- already-stored section_ui_schema JSON in place.
--
-- Poultry (chicken, duck, ...) and Beehive animals have no ear to attach a
-- tag to, so on the Livestock Details form (ls_animal_details_table,
-- panels[0].panels[0].widgets[0].widget-data-columns):
--   1. the "ear_tag_id" column (index 0) is no longer unconditionally
--      required — it's now hidden and not required for those two species,
--      required otherwise;
--   2. a new "secondary_identifier" column is inserted right after it
--      (index 1) — a free-text leg band / wing tag / hive number, shown and
--      required only for those two species.
-- See G2PRegisterDomainServiceAnimal._EAR_TAG_EXEMPT_SPECIES for the
-- matching backend-side enforcement, which does not depend on this form
-- config being in place (so this patch is a UX fix, not a correctness one).
--
-- Each statement's WHERE clause double-checks the path it touches still
-- holds what it expects (protects against the shape having drifted since
-- this was written) and, for the ear_tag_id update, that it hasn't already
-- been patched (safe to re-run). The secondary_identifier insert is guarded
-- by NOT (... ? 'secondary_identifier') so re-running this file doesn't
-- insert a second copy of the column.

-- 1. Replace the ear_tag_id column object (index 0) with the
--    species-conditional version.
UPDATE g2p_register_sections
SET section_ui_schema = jsonb_set(
    section_ui_schema,
    '{panels,0,panels,0,widgets,0,widget-data-columns,0}',
    '{"widget": "text", "column-key": "ear_tag_id", "widget-type": "input", "widget-label": "Livestock Ear Tag", "widget-readonly": false, "widget-data-path": "ear_tag_id", "widget-required": false, "widget-data-options": {"actions": [{"action": "hide", "condition": {"field": "species", "operator": "in", "value": ["LIVESTOCK_SPECIES_POULTRY", "LIVESTOCK_SPECIES_BEEHIVE"]}}, {"action": "require", "condition": {"field": "species", "operator": "notIn", "value": ["LIVESTOCK_SPECIES_POULTRY", "LIVESTOCK_SPECIES_BEEHIVE"]}}]}}'::jsonb
)
WHERE register_id = '997676d3-7008-59f9-b23e-613ad79bbb08'
  AND section_id = 'livestock_animal_details_section_01'
  AND section_ui_schema #>> '{panels,0,panels,0,widgets,0,widget-data-columns,0,column-key}' = 'ear_tag_id'
  AND NOT (section_ui_schema #> '{panels,0,panels,0,widgets,0,widget-data-columns,0}') ? 'widget-data-options';

-- 2. Insert the new secondary_identifier column right after it (index 1),
--    shifting species/breed/... down by one.
UPDATE g2p_register_sections
SET section_ui_schema = jsonb_insert(
    section_ui_schema,
    '{panels,0,panels,0,widgets,0,widget-data-columns,1}',
    '{"widget": "text", "column-key": "secondary_identifier", "widget-type": "input", "widget-label": "Secondary Identifier", "widget-readonly": false, "widget-data-path": "secondary_identifier", "widget-data-placeholder": "Leg band / wing tag / hive no.", "widget-required": false, "widget-data-options": {"actions": [{"action": "show", "condition": {"field": "species", "operator": "in", "value": ["LIVESTOCK_SPECIES_POULTRY", "LIVESTOCK_SPECIES_BEEHIVE"]}}, {"action": "require", "condition": {"field": "species", "operator": "in", "value": ["LIVESTOCK_SPECIES_POULTRY", "LIVESTOCK_SPECIES_BEEHIVE"]}}]}}'::jsonb,
    false
)
WHERE register_id = '997676d3-7008-59f9-b23e-613ad79bbb08'
  AND section_id = 'livestock_animal_details_section_01'
  AND NOT (section_ui_schema #> '{panels,0,panels,0,widgets,0,widget-data-columns}')
      @> '[{"column-key": "secondary_identifier"}]';
