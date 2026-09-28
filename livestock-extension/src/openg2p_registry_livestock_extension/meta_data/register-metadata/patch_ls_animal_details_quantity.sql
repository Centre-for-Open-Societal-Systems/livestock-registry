-- Patch for already-seeded environments only (see
-- patch_ls_animal_details_species_identifier.sql for the same pattern this
-- follows, and for why this only fixes UX — the domain service enforces the
-- underlying rule regardless of this JSON).
--
-- Follow-up to patch_ls_animal_details_species_identifier.sql: poultry and
-- beehive are recorded as a flock/hive with a head count, not one row per
-- animal. On the Livestock Details form
-- (panels[0].panels[0].widgets[0].widget-data-columns):
--   1. the "secondary_identifier" column's placeholder is reworded to name
--      a flock/batch/hive rather than a single bird's tag;
--   2. a new "quantity" column is inserted right after "breed" — shown and
--      required only for poultry/beehive, same show/require pattern as
--      secondary_identifier.
--
-- Assumes patch_ls_animal_details_species_identifier.sql has already been
-- applied (secondary_identifier present at index 1) — this file's WHERE
-- clauses check that and no-op otherwise, rather than silently building on
-- a shape that isn't there. Safe to re-run: the quantity insert is guarded
-- by NOT (... ? 'quantity').

-- 1. Reword the secondary_identifier placeholder.
UPDATE g2p_register_sections
SET section_ui_schema = jsonb_set(
    section_ui_schema,
    '{panels,0,panels,0,widgets,0,widget-data-columns,1,widget-data-placeholder}',
    '"Flock / Batch / Hive ID (e.g. FLOCK-2026-01)"'::jsonb
)
WHERE register_id = '997676d3-7008-59f9-b23e-613ad79bbb08'
  AND section_id = 'livestock_animal_details_section_01'
  AND section_ui_schema #>> '{panels,0,panels,0,widgets,0,widget-data-columns,1,column-key}' = 'secondary_identifier';

-- 2. Insert the new quantity column right after breed (index 3), shifting
--    weight/date_of_birth/... down by one.
UPDATE g2p_register_sections
SET section_ui_schema = jsonb_insert(
    section_ui_schema,
    '{panels,0,panels,0,widgets,0,widget-data-columns,4}',
    '{"widget": "number", "column-key": "quantity", "widget-type": "input", "widget-label": "Quantity (Head Count)", "widget-readonly": false, "widget-data-path": "quantity", "widget-data-format": {"textAlign": "right"}, "widget-required": false, "widget-data-options": {"actions": [{"action": "show", "condition": {"field": "species", "operator": "in", "value": ["LIVESTOCK_SPECIES_POULTRY", "LIVESTOCK_SPECIES_BEEHIVE"]}}, {"action": "require", "condition": {"field": "species", "operator": "in", "value": ["LIVESTOCK_SPECIES_POULTRY", "LIVESTOCK_SPECIES_BEEHIVE"]}}]}}'::jsonb,
    false
)
WHERE register_id = '997676d3-7008-59f9-b23e-613ad79bbb08'
  AND section_id = 'livestock_animal_details_section_01'
  AND section_ui_schema #>> '{panels,0,panels,0,widgets,0,widget-data-columns,3,column-key}' = 'breed'
  AND NOT (section_ui_schema #> '{panels,0,panels,0,widgets,0,widget-data-columns}')
      @> '[{"column-key": "quantity"}]';
