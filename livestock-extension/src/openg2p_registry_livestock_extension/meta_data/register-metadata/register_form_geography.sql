-- Normalize the legacy panel ID without adding a second holding map.
UPDATE g2p_register_sections SET section_ui_schema = replace(section_ui_schema::text, 'coss_location_widgets', 'location_widgets')::jsonb
WHERE section_id = 'livestock_livestock_location_section_03' AND section_ui_schema::text LIKE '%coss_location_widgets%';
