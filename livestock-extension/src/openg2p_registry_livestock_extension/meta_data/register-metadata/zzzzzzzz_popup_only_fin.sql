-- Final UI-only projection: FIN is supplied through Verify with Fayda.
-- Retain every field/path and the separate editable 16-digit FAN alternative.
CREATE OR REPLACE FUNCTION pg_temp.oan_popup_only_fin(node jsonb)
RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE result jsonb;
BEGIN
  IF jsonb_typeof(node) = 'array' THEN
    SELECT COALESCE(jsonb_agg(pg_temp.oan_popup_only_fin(value) ORDER BY position), '[]'::jsonb)
      INTO result FROM jsonb_array_elements(node) WITH ORDINALITY AS item(value, position);
  ELSIF jsonb_typeof(node) = 'object' THEN
    SELECT COALESCE(jsonb_object_agg(key, pg_temp.oan_popup_only_fin(value)), '{}'::jsonb)
      INTO result FROM jsonb_each(node);
    IF node ? 'widget' AND (node->>'widget-id' = 'fayda_fin'
        OR node->>'widget-data-path' LIKE '%.fayda_fin') THEN
      result := (result - 'widget-data-placeholder' - 'widget-data-options' - 'widget-data-validation')
        || '{"widget":"display","widget-type":"display","widget-readonly":true,
             "widget-required":false,"widget-label":"Fayda FIN (from verification)"}'::jsonb;
    END IF;
  ELSE
    result := node;
  END IF;
  RETURN result;
END $$;
UPDATE g2p_register_sections SET section_ui_schema = pg_temp.oan_popup_only_fin(section_ui_schema)
WHERE section_ui_schema IS NOT NULL;
-- Earlier popup patches can match both the profile's id-path and the input
-- panel. Remove repeated identity controls once per section, retaining every
-- other widget (profile/name/projection/season) and the first control's paths.
CREATE OR REPLACE FUNCTION pg_temp.oan_unique_identity_widgets(node jsonb, seen jsonb DEFAULT '{}'::jsonb)
RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE result jsonb; child record; part jsonb; widget_id text;
BEGIN
  IF jsonb_typeof(node) = 'object' AND node ? 'widget' THEN
    widget_id := node->>'widget-id';
    IF widget_id = ANY(ARRAY['farmer_id','fayda_fin','fayda_fan_id','identity_verification','farmer_reference_status']) THEN
      IF seen ? widget_id THEN
        RETURN jsonb_build_object('node', NULL, 'seen', seen, 'omit', true);
      END IF;
      seen := seen || jsonb_build_object(widget_id, true);
    END IF;
  END IF;
  IF jsonb_typeof(node) = 'array' THEN
    result := '[]'::jsonb;
    FOR child IN SELECT value FROM jsonb_array_elements(node) WITH ORDINALITY AS a(value, ord) ORDER BY ord LOOP
      part := pg_temp.oan_unique_identity_widgets(child.value, seen);
      seen := part->'seen';
      IF NOT COALESCE((part->>'omit')::boolean, false) THEN
        result := result || jsonb_build_array(part->'node');
      END IF;
    END LOOP;
  ELSIF jsonb_typeof(node) = 'object' THEN
    result := '{}'::jsonb;
    FOR child IN SELECT key, value FROM jsonb_each(node) ORDER BY key LOOP
      part := pg_temp.oan_unique_identity_widgets(child.value, seen);
      seen := part->'seen';
      result := result || jsonb_build_object(child.key, part->'node');
    END LOOP;
  ELSE
    result := node;
  END IF;
  RETURN jsonb_build_object('node', result, 'seen', seen);
END $$;
UPDATE g2p_register_sections SET section_ui_schema = pg_temp.oan_unique_identity_widgets(section_ui_schema)->'node'
WHERE section_id IN ('livestock_livestock_record_section_01','livestock_intake_identity_section_01');
DO $$ BEGIN
  IF EXISTS (SELECT s.section_id, w->>'widget-id'
      FROM g2p_register_sections s, jsonb_path_query(s.section_ui_schema, 'strict $.**') w
      WHERE s.section_id IN ('livestock_livestock_record_section_01','livestock_intake_identity_section_01')
        AND jsonb_typeof(w) = 'object' AND w ? 'widget'
        AND w->>'widget-id' IN ('farmer_id','fayda_fin','fayda_fan_id','identity_verification','farmer_reference_status')
      GROUP BY s.section_id, w->>'widget-id' HAVING count(*) <> 1) THEN
    RAISE EXCEPTION 'Registered and intake identity controls must occur exactly once per section';
  END IF;
  IF EXISTS (SELECT 1 FROM g2p_register_sections s,
      jsonb_path_query(s.section_ui_schema, 'strict $.**') w
      WHERE jsonb_typeof(w) = 'object' AND w ? 'widget'
        AND (w->>'widget-id' = 'fayda_fin' OR w->>'widget-data-path' LIKE '%.fayda_fin')
        AND (w->>'widget' IS DISTINCT FROM 'display'
          OR w->>'widget-readonly' IS DISTINCT FROM 'true'
          OR w->>'widget-required' IS DISTINCT FROM 'false')) THEN
    RAISE EXCEPTION 'FIN on intake and register forms must be a read-only verification projection';
  END IF;
END $$;
