-- Patch for already-seeded environments only (see
-- patch_ls_animal_details_species_identifier.sql for the pattern this
-- follows).
--
-- Neither Date of Birth nor Gender fits a _FLOCK_SPECIES row (poultry,
-- beehive) cleanly: a flock of 500 birds has no single hatch date and isn't
-- one sex. On the Livestock Details form
-- (panels[0].panels[0].widgets[0].widget-data-columns):
--   1. "date_of_birth" (index 6) is no longer unconditionally required —
--      required for an individually-tracked species same as before, not
--      required for poultry/beehive. No named mandatory-constraint on this
--      field, so it's dropped outright rather than needing an escape hatch.
--   2. "gender" (index 8) stays required for every species (G2R-135) — a
--      third "Mixed / Not Applicable" option is added to its dropdown so a
--      flock row can answer it honestly instead of picking an arbitrary
--      MALE/FEMALE for a mixed group. GenderEnum.MIXED
--      (register_domain/models/enums.py) must already be deployed
--      (staff-api rebuilt) before this value is accepted on save.
--
-- Each statement's WHERE clause checks the index it touches still holds
-- what it expects and, where applicable, that it hasn't already been
-- patched (safe to re-run).

-- 1. date_of_birth: no longer unconditionally required.
UPDATE g2p_register_sections
SET section_ui_schema = jsonb_set(
    jsonb_set(
        section_ui_schema,
        '{panels,0,panels,0,widgets,0,widget-data-columns,6,widget-required}',
        'false'::jsonb
    ),
    '{panels,0,panels,0,widgets,0,widget-data-columns,6,widget-data-options}',
    '{"actions": [{"action": "require", "condition": {"field": "species", "operator": "notIn", "value": ["LIVESTOCK_SPECIES_POULTRY", "LIVESTOCK_SPECIES_BEEHIVE"]}}]}'::jsonb
)
WHERE register_id = '997676d3-7008-59f9-b23e-613ad79bbb08'
  AND section_id = 'livestock_animal_details_section_01'
  AND section_ui_schema #>> '{panels,0,panels,0,widgets,0,widget-data-columns,6,column-key}' = 'date_of_birth'
  AND NOT (section_ui_schema #> '{panels,0,panels,0,widgets,0,widget-data-columns,6}') ? 'widget-data-options';

-- 2. gender: append the "Mixed / Not Applicable" option.
UPDATE g2p_register_sections
SET section_ui_schema = jsonb_set(
    section_ui_schema,
    '{panels,0,panels,0,widgets,0,widget-data-columns,8,widget-data-source,options}',
    (section_ui_schema #> '{panels,0,panels,0,widgets,0,widget-data-columns,8,widget-data-source,options}')
        || '[{"label": "Mixed / Not Applicable", "value": "MIXED"}]'::jsonb
)
WHERE register_id = '997676d3-7008-59f9-b23e-613ad79bbb08'
  AND section_id = 'livestock_animal_details_section_01'
  AND section_ui_schema #>> '{panels,0,panels,0,widgets,0,widget-data-columns,8,column-key}' = 'gender'
  AND NOT (section_ui_schema #> '{panels,0,panels,0,widgets,0,widget-data-columns,8,widget-data-source,options}')
      @> '[{"value": "MIXED"}]';
