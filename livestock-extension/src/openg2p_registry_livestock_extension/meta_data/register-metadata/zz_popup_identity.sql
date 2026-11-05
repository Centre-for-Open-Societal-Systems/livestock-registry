-- Typed Fayda FIN input next to the Farmer ID. UID/FAN16 remains distinct.
CREATE OR REPLACE FUNCTION pg_temp.oan_popup_identity(node jsonb)
RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE result jsonb;
BEGIN
  IF jsonb_typeof(node)='array' THEN
    SELECT COALESCE(jsonb_agg(pg_temp.oan_popup_identity(value) ORDER BY ord),'[]'::jsonb)
      INTO result FROM jsonb_array_elements(node) WITH ORDINALITY AS a(value,ord);
  ELSIF jsonb_typeof(node)='object' THEN
    SELECT COALESCE(jsonb_object_agg(key,pg_temp.oan_popup_identity(value)),'{}'::jsonb)
      INTO result FROM jsonb_each(node);
    IF node->>'widget-data-path' = '997676d3-7008-59f9-b23e-613ad79bbb08.foundational_id' THEN
      result := result || '{"widget":"display","widget-type":"display","widget-readonly":true,"widget-required":false}'::jsonb;
    END IF;
    IF jsonb_typeof(node->'widgets')='array'
       AND (node->'widgets')::text LIKE '%997676d3-7008-59f9-b23e-613ad79bbb08.farmer_id%'
       AND NOT jsonb_path_exists(node->'widgets','lax $.** ? (@."widget-id" == "fayda_fin")') THEN
      result := jsonb_set(result,'{widgets}',result->'widgets' || jsonb_build_array('{"widget": "text", "widget-id": "fayda_fin", "widget-type": "input", "widget-label": "Fayda FIN (12 digits, optional)", "widget-readonly": false, "widget-required": false, "widget-data-path": "997676d3-7008-59f9-b23e-613ad79bbb08.fayda_fin", "widget-data-placeholder": "12-digit FIN", "widget-data-validation": {"pattern": "^[0-9]{12}$", "patternMessage": "Fayda FIN: enter exactly 12 digits, or use the separate 16-digit FAN field."}}'::jsonb));
    END IF;
  ELSE result:=node;
  END IF;
  RETURN result;
END $$;
UPDATE g2p_register_sections SET section_ui_schema=pg_temp.oan_popup_identity(section_ui_schema)
WHERE section_ui_schema IS NOT NULL;
