-- Patch for already-seeded environments only (see
-- patch_ls_animal_details_dynamic_species_config.sql for the pattern this
-- follows).
--
-- Adds "widget-badge-colors" to the Livestock Details animals table's
-- health_status column, so its read-only table-cell value (TableWidget's
-- SelectDisplayValue, ui-widgets — requires the staff-ui rebuild described
-- in [[livestock-staff-ui-docker-rebuild]] to be live; this SQL patch alone
-- does nothing without it) renders as a colored pill instead of plain text:
-- HEALTHY green, SICK yellow, QUARANTINED orange, DECEASED red. Gives staff
-- an at-a-glance read of an animal's health without opening its row, and
-- makes a Mortality/Disease Vital Event's automatic health_status side
-- effect (see G2PRegisterDomainServiceVitalEvent._sync_animal_health_status)
-- visible immediately on the Livestock record.
--
-- widget-data-columns index (panels[0].panels[0].widgets[0]): 9 health_status.
-- The WHERE clause double-checks the index still holds that column,
-- protecting against the shape having drifted since this was written. Safe
-- to re-run (a full replace of the key, not a merge).

UPDATE g2p_register_sections
SET section_ui_schema = jsonb_set(
    section_ui_schema,
    '{panels,0,panels,0,widgets,0,widget-data-columns,9,widget-badge-colors}',
    '{"HEALTHY": "green", "SICK": "yellow", "QUARANTINED": "orange", "DECEASED": "red"}'::jsonb
)
WHERE register_id = '997676d3-7008-59f9-b23e-613ad79bbb08'
  AND section_id = 'livestock_animal_details_section_01'
  AND section_ui_schema #>> '{panels,0,panels,0,widgets,0,widget-data-columns,9,column-key}' = 'health_status';
