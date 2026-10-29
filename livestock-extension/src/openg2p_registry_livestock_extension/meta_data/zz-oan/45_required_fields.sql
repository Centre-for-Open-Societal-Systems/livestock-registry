-- Mandatory Livestock fields beyond the Farmer lookup and the animal table
-- (those are marked by 10_farmer_lookup.sql and the animal-row file): the
-- surveyor who collected the data and the livestock location. The intake service
-- (required_intake.py) reads `widget-required` and refuses "Next" and Submit for
-- every channel, so this file only marks the widgets.
--
-- Only the widget-required key of each widget is set, found by widget-id inside
-- the section JSON, so the layout files (40_*) and label files survive.
-- Supervisor name and mobile numbers stay optional. The Farmer register's own
-- sections are not part of the Livestock intake and are not touched.
-- Idempotent: it only sets the flag to true; explicit ids only.
CREATE OR REPLACE FUNCTION pg_temp.coss_require_widgets(node jsonb, ids text[])
RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE result jsonb;
BEGIN
  IF jsonb_typeof(node) = 'array' THEN
    SELECT COALESCE(jsonb_agg(pg_temp.coss_require_widgets(value, ids) ORDER BY position), '[]'::jsonb)
      INTO result FROM jsonb_array_elements(node) WITH ORDINALITY AS item(value, position);
  ELSIF jsonb_typeof(node) = 'object' THEN
    SELECT COALESCE(jsonb_object_agg(key, pg_temp.coss_require_widgets(value, ids)), '{}'::jsonb)
      INTO result FROM jsonb_each(node);
    IF node ? 'widget' AND node->>'widget-id' = ANY (ids) THEN
      result := result || '{"widget-required": true}'::jsonb;
    END IF;
  ELSE
    result := node;
  END IF;
  RETURN result;
END $$;

UPDATE g2p_register_sections
SET section_ui_schema = pg_temp.coss_require_widgets(section_ui_schema::jsonb, ARRAY['surveyor_name'])
WHERE section_id = 'livestock_survey_personnel_section_02' AND section_ui_schema IS NOT NULL;

UPDATE g2p_register_sections
SET section_ui_schema = pg_temp.coss_require_widgets(section_ui_schema::jsonb, ARRAY['livestock_geo_hierarchy'])
WHERE section_id = 'livestock_livestock_location_section_03' AND section_ui_schema IS NOT NULL;

-- Check: fail the seed loudly if a mandatory widget is missing or optional.
DO $$
DECLARE wanted record; node jsonb;
BEGIN
  FOR wanted IN SELECT * FROM (VALUES
      ('livestock_survey_personnel_section_02', 'surveyor_name'),
      ('livestock_livestock_location_section_03', 'livestock_geo_hierarchy')) AS w(section_id, widget_id)
  LOOP
    SELECT n INTO node FROM g2p_register_sections s,
      jsonb_path_query(s.section_ui_schema::jsonb, 'strict $.**') n
      WHERE s.section_id = wanted.section_id AND jsonb_typeof(n) = 'object'
        AND n->>'widget-id' = wanted.widget_id AND n ? 'widget';
    IF node IS NULL OR node->'widget-required' IS DISTINCT FROM 'true'::jsonb THEN
      RAISE EXCEPTION 'widget % of % must be widget-required', wanted.widget_id, wanted.section_id;
    END IF;
  END LOOP;
END $$;
