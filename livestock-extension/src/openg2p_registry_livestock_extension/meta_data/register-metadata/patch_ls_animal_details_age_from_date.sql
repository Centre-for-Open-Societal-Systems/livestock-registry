-- Patch for already-seeded environments only.
--
-- g2p_register_sections.sql is a one-shot db-seed INSERT, so it only applies
-- on a fresh database. An environment that was seeded before the "age" column
-- in ls_animal_details gained live "widget-age-from-date" support (see
-- g2p_register_sections.sql, section livestock_animal_details_section_01)
-- needs this UPDATE instead, to patch the already-stored section_ui_schema
-- JSON in place.
--
-- It merges {"widget-age-from-date": {"baseField": "date_of_birth"}} into the
-- existing "age" column object at
-- panels[0].panels[0].widgets[0].widget-data-columns[5], without touching any
-- other part of the schema. The WHERE clause double-checks that index really
-- holds the "age" column (protects against the path having drifted since this
-- was written) and that the key isn't already present (safe to re-run).

UPDATE g2p_register_sections
SET section_ui_schema = jsonb_set(
    section_ui_schema,
    '{panels,0,panels,0,widgets,0,widget-data-columns,5}',
    (section_ui_schema #> '{panels,0,panels,0,widgets,0,widget-data-columns,5}')
        || '{"widget-age-from-date": {"baseField": "date_of_birth"}}'::jsonb
)
WHERE register_id = '997676d3-7008-59f9-b23e-613ad79bbb08'
  AND section_id = 'livestock_animal_details_section_01'
  AND section_ui_schema #>> '{panels,0,panels,0,widgets,0,widget-data-columns,5,column-key}' = 'age'
  AND NOT (section_ui_schema #> '{panels,0,panels,0,widgets,0,widget-data-columns,5}') ? 'widget-age-from-date';
