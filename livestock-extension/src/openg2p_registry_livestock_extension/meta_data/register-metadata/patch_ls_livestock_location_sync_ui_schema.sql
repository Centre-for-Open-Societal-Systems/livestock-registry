-- Patch for already-seeded environments only.
--
-- Syncs the livestock_livestock_location_section_03 section_ui_schema to the canonical definition in
-- g2p_register_sections.sql (the seed only INSERTs and never touches an
-- existing row).
--
-- Why: the location is the native geo-hierarchy widget bound to the register's
-- geo_lowest_level_value_id / geo_code_hierarchy_json (Master Data geo unit ids,
-- P-codes). region_id ... kebele_id and the names are filled from the hierarchy on
-- save (register_domain/services/admin_area_sync.py).
UPDATE "public"."g2p_register_sections"
SET "section_ui_schema" = '{"section-required-for-submit": false, "section-title": "Location", "panels": [{"panels": [{"widgets": [{"widget": "geo-hierarchy", "widget-id": "livestock_geo_hierarchy", "widget-type": "input", "widget-label": "Administrative hierarchy", "widget-readonly": false, "widget-required": false, "widget-data-path": {"value": "997676d3-7008-59f9-b23e-613ad79bbb08.geo_lowest_level_value_id", "hierarchy": "997676d3-7008-59f9-b23e-613ad79bbb08.geo_code_hierarchy_json"}, "widget-data-source": {"type": "api", "method": "POST", "service": "master-data", "levelsEndpoint": "get-all-g2p-geo-levels", "valuesEndpoint": "geo-level-values"}, "widget-geo-layout": {"columnSpan": 1}}], "panel-id": "vertical_panel_ls_livestock_location_1", "panel-orientation": "vertical"}], "panel-id": "horizontal_panel_ls_livestock_location", "panel-orientation": "horizontal"}, {"panel-id": "location_widgets", "panel-orientation": "vertical", "widgets": [{"widget": "oan-geo-point", "widget-id": "livestock_geo_point", "widget-type": "input", "widget-label": "Holding location", "widget-required": false, "widget-readonly": false, "widget-data-path": {"latitude": "997676d3-7008-59f9-b23e-613ad79bbb08.latitude", "longitude": "997676d3-7008-59f9-b23e-613ad79bbb08.longitude", "hierarchy": "997676d3-7008-59f9-b23e-613ad79bbb08.geo_code_hierarchy_json", "location": "997676d3-7008-59f9-b23e-613ad79bbb08.geo_lowest_level_value_id"}, "widget-data-format": {"bounds": [[3.3, 32.9], [15.0, 48.1]], "minZoom": 5, "height": 420, "boundaries": {"url": "/api/master-data/geo-boundary?level=woreda", "geoSource": {"method": "POST", "service": "master-data", "levelsEndpoint": "get-all-g2p-geo-levels", "valuesEndpoint": "geo-level-values"}}}}]}]}'
WHERE "section_id" = 'livestock_livestock_location_section_03';
