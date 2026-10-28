-- The holding map (oan-geo-point) next to the Location section's geo-hierarchy widget;
-- both read and write the register's geo_lowest_level_value_id / geo_code_hierarchy_json.
-- Registered widgets and native Master Data only; no identity grants or geo resolvers.
UPDATE g2p_register_sections SET section_ui_schema = jsonb_set(section_ui_schema::jsonb, '{panels}',
  COALESCE(section_ui_schema::jsonb->'panels','[]'::jsonb) || '[{"panel-id":"coss_location_widgets","panel-orientation":"vertical","widgets":[{"widget":"oan-geo-point","widget-id":"livestock_geo_point","widget-type":"input","widget-label":"Holding location","widget-required":false,"widget-readonly":false,"widget-data-path":{"latitude":"997676d3-7008-59f9-b23e-613ad79bbb08.latitude","longitude":"997676d3-7008-59f9-b23e-613ad79bbb08.longitude","hierarchy":"997676d3-7008-59f9-b23e-613ad79bbb08.geo_code_hierarchy_json","location":"997676d3-7008-59f9-b23e-613ad79bbb08.geo_lowest_level_value_id"},"widget-data-format":{"bounds":[[3.3,32.9],[15.0,48.1]],"minZoom":5,"height":420,"boundaries":{"url":"/api/master-data/geo-boundary?level=woreda","geoSource":{"method":"POST","service":"master-data","levelsEndpoint":"get-all-g2p-geo-levels","valuesEndpoint":"geo-level-values"}}}}]}]'::jsonb)
WHERE section_id = 'livestock_livestock_location_section_03'
  AND NOT EXISTS (SELECT 1 FROM jsonb_array_elements(COALESCE(section_ui_schema::jsonb->'panels','[]'::jsonb)) panel
                  WHERE panel->>'panel-id' = 'coss_location_widgets');
