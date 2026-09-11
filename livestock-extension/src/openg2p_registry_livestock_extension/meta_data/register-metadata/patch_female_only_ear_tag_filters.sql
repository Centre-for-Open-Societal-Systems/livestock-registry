-- Patch for already-seeded environments only (see
-- patch_ls_animal_details_health_status_badges.sql for the pattern this
-- follows).
--
-- Only a female animal can be bred or give birth, so the Ear Tag dropdown
-- in these two dialog-table forms (both a `sibling-table` data source
-- reading rows already entered under Livestock Details in the same
-- submission — see SiblingTableDataSource in ui-widgets/src/types) now
-- filters to gender = FEMALE:
--
-- 1. Breeding Details: unconditional — every Breeding row is about a dam,
--    so its Ear Tag dropdown is always female-only.
-- 2. Vital Event Details: conditional on the SAME row's own Event Type —
--    female-only when Event Type = BIRTH, but unfiltered (any animal) for
--    MORTALITY/DISEASE, which apply to either sex. The `when` clause makes
--    this live per-row: DialogTableField/TableCellSelect (ui-widgets)
--    inject the current row's own field values as `widget-row-context`, and
--    useBaseWidget/getSiblingTableDataSource re-filter the options the
--    moment Event Type changes — requires the staff-ui rebuild described in
--    [[livestock-staff-ui-docker-rebuild]] to be live; this SQL patch alone
--    does nothing without it.
--
-- widget-data-columns index (panels[0].panels[0].widgets[0]) is 0
-- (ear_tag_id) in both sections. Each WHERE clause double-checks the index
-- still holds that column, protecting against the shape having drifted
-- since this was written. Safe to re-run (a full replace of the key, not a
-- merge).

UPDATE g2p_register_sections
SET section_ui_schema = jsonb_set(
    section_ui_schema,
    '{panels,0,panels,0,widgets,0,widget-data-columns,0,widget-data-source,optionFilter}',
    '{"field": "gender", "operator": "equals", "value": "FEMALE"}'::jsonb
)
WHERE section_id = 'livestock_breeding_details_section_01'
  AND section_ui_schema #>> '{panels,0,panels,0,widgets,0,widget-data-columns,0,column-key}' = 'ear_tag_id';

UPDATE g2p_register_sections
SET section_ui_schema = jsonb_set(
    section_ui_schema,
    '{panels,0,panels,0,widgets,0,widget-data-columns,0,widget-data-source,optionFilter}',
    '{"field": "gender", "operator": "equals", "value": "FEMALE", "when": {"field": "event_type", "operator": "equals", "value": "BIRTH"}}'::jsonb
)
WHERE section_id = 'livestock_vital_event_details_section_01'
  AND section_ui_schema #>> '{panels,0,panels,0,widgets,0,widget-data-columns,0,column-key}' = 'ear_tag_id';
