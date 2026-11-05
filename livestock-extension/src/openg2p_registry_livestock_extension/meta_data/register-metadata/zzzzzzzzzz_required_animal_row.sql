-- Each Livestock intake needs at least one animal row. The intake service
-- (required_intake.py) enforces `widget-required` on save and submit for every
-- channel, so this file only marks the widget.
--
-- Animal table (dialog-table widget id): ls_animal_details_table, section
-- livestock_animal_details_section_01. Its columns keep the flags the earlier
-- files give them (species, breed, gender, health status, vaccination status,
-- registration date). The event tables (health, vaccination, vital, breeding)
-- stay optional.
--
-- Sorts after every earlier file that rewrites the section JSON (the base
-- upsert, the animal-details patches, field rules, identity overlays); no later
-- file touches this section.
-- Idempotent: it only sets the flag to true, so every install and upgrade can re-run it.
CREATE OR REPLACE FUNCTION pg_temp.coss_require_animal_row(node jsonb, table_id text)
RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE result jsonb;
BEGIN
  IF jsonb_typeof(node) = 'array' THEN
    SELECT COALESCE(jsonb_agg(pg_temp.coss_require_animal_row(value, table_id) ORDER BY position), '[]'::jsonb)
      INTO result FROM jsonb_array_elements(node) WITH ORDINALITY AS item(value, position);
  ELSIF jsonb_typeof(node) = 'object' THEN
    SELECT COALESCE(jsonb_object_agg(key, pg_temp.coss_require_animal_row(value, table_id)), '{}'::jsonb)
      INTO result FROM jsonb_each(node);
    IF node->>'widget-id' = table_id AND node->>'widget' IN ('table', 'dialog-table') THEN
      result := result || '{"widget-required": true}'::jsonb;
    END IF;
  ELSE
    result := node;
  END IF;
  RETURN result;
END $$;

UPDATE g2p_register_sections
SET section_ui_schema = pg_temp.coss_require_animal_row(section_ui_schema::jsonb, 'ls_animal_details_table')
WHERE section_id = 'livestock_animal_details_section_01' AND section_ui_schema IS NOT NULL;

-- Check: fail the seed loudly if the animal table is missing or not required.
DO $$
DECLARE table_node jsonb;
BEGIN
  SELECT w INTO table_node FROM g2p_register_sections s,
    jsonb_path_query(s.section_ui_schema::jsonb, 'strict $.**') w
    WHERE s.section_id = 'livestock_animal_details_section_01' AND jsonb_typeof(w) = 'object'
      AND w->>'widget-id' = 'ls_animal_details_table';
  IF table_node IS NULL OR table_node->'widget-required' IS DISTINCT FROM 'true'::jsonb THEN
    RAISE EXCEPTION 'animal table ls_animal_details_table of livestock_animal_details_section_01 must be widget-required';
  END IF;
END $$;
