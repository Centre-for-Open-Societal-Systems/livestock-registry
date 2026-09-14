-- Patch for already-seeded environments only (see
-- patch_ls_animal_details_species_identifier.sql for the pattern this
-- follows).
--
-- Replaces the hardcoded ["LIVESTOCK_SPECIES_POULTRY", "LIVESTOCK_SPECIES_BEEHIVE"]
-- value lists on ear_tag_id/secondary_identifier/quantity/date_of_birth's
-- widget-data-options conditions with a live reference to the selected
-- species' own "Requires Ear Tag" / "Flock / Group Species" config
-- (Configuration > Attributes > Species > Edit), via the new
-- `species__raw.<property>` condition-field support added to
-- DialogTableWidget's buildDialogConditionValues (ui-widgets, requires the
-- staff-ui rebuild described in [[livestock-staff-ui-docker-rebuild]] to be
-- live — this SQL patch alone does nothing without it). Fixes the gap where
-- a brand-new species (e.g. "Duck") configured with Requires Ear Tag
-- unchecked still showed the old hardcoded Ear Tag/DOB-required,
-- Quantity/Secondary-Identifier-hidden behavior on this form, because the
-- old conditions only ever matched the two species value_ids baked in here
-- at the time this form was first built.
--
-- widget-data-columns indices (panels[0].panels[0].widgets[0]):
--   0 ear_tag_id, 1 secondary_identifier, 4 quantity, 6 date_of_birth.
-- Each WHERE clause double-checks the index still holds the column it
-- expects, protecting against the shape having drifted since this was
-- written. Safe to re-run (each is a full replace of that column's
-- widget-data-options, not a merge).

UPDATE g2p_register_sections
SET section_ui_schema = jsonb_set(
    section_ui_schema,
    '{panels,0,panels,0,widgets,0,widget-data-columns,0,widget-data-options}',
    '{"actions": [{"action": "hide", "condition": {"field": "species__raw.requires_ear_tag", "operator": "equals", "value": false}}, {"action": "require", "condition": {"field": "species__raw.requires_ear_tag", "operator": "notEquals", "value": false}}]}'::jsonb
)
WHERE register_id = '997676d3-7008-59f9-b23e-613ad79bbb08'
  AND section_id = 'livestock_animal_details_section_01'
  AND section_ui_schema #>> '{panels,0,panels,0,widgets,0,widget-data-columns,0,column-key}' = 'ear_tag_id';

UPDATE g2p_register_sections
SET section_ui_schema = jsonb_set(
    section_ui_schema,
    '{panels,0,panels,0,widgets,0,widget-data-columns,1,widget-data-options}',
    '{"actions": [{"action": "show", "condition": {"field": "species__raw.requires_ear_tag", "operator": "equals", "value": false}}, {"action": "require", "condition": {"field": "species__raw.requires_ear_tag", "operator": "equals", "value": false}}]}'::jsonb
)
WHERE register_id = '997676d3-7008-59f9-b23e-613ad79bbb08'
  AND section_id = 'livestock_animal_details_section_01'
  AND section_ui_schema #>> '{panels,0,panels,0,widgets,0,widget-data-columns,1,column-key}' = 'secondary_identifier';

UPDATE g2p_register_sections
SET section_ui_schema = jsonb_set(
    section_ui_schema,
    '{panels,0,panels,0,widgets,0,widget-data-columns,4,widget-data-options}',
    '{"actions": [{"action": "show", "condition": {"field": "species__raw.is_flock_species", "operator": "equals", "value": true}}, {"action": "require", "condition": {"field": "species__raw.is_flock_species", "operator": "equals", "value": true}}]}'::jsonb
)
WHERE register_id = '997676d3-7008-59f9-b23e-613ad79bbb08'
  AND section_id = 'livestock_animal_details_section_01'
  AND section_ui_schema #>> '{panels,0,panels,0,widgets,0,widget-data-columns,4,column-key}' = 'quantity';

UPDATE g2p_register_sections
SET section_ui_schema = jsonb_set(
    section_ui_schema,
    '{panels,0,panels,0,widgets,0,widget-data-columns,6,widget-data-options}',
    '{"actions": [{"action": "require", "condition": {"field": "species__raw.is_flock_species", "operator": "notEquals", "value": true}}]}'::jsonb
)
WHERE register_id = '997676d3-7008-59f9-b23e-613ad79bbb08'
  AND section_id = 'livestock_animal_details_section_01'
  AND section_ui_schema #>> '{panels,0,panels,0,widgets,0,widget-data-columns,6,column-key}' = 'date_of_birth';
