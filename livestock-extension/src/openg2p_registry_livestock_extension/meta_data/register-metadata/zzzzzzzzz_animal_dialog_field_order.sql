-- The Livestock Details dialog asks Species and Breed before the Ear Tag
-- because which identifier an animal carries depends on its species
-- (an ear tag, or a secondary identifier for poultry and beehives).
--
-- Only the order of the animal table's columns changes, found by its widget-id
-- inside the section JSON; the columns themselves, and every other key the
-- earlier files set on them, are kept as they are. Species and Breed move to
-- the front, the other columns keep their order. The table shows its columns in
-- the same order. Idempotent: a second run finds them in front already.
-- Sorts after the patch_ls_* files that rewrite the section and before
-- zzzzzzzzzz_required_animal_row.sql, which must stay the last file touching it.
CREATE OR REPLACE FUNCTION pg_temp.oan_species_breed_first(node jsonb)
RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE result jsonb; cols jsonb;
BEGIN
  IF jsonb_typeof(node) = 'array' THEN
    SELECT COALESCE(jsonb_agg(pg_temp.oan_species_breed_first(value) ORDER BY position), '[]'::jsonb)
      INTO result FROM jsonb_array_elements(node) WITH ORDINALITY AS item(value, position);
  ELSIF jsonb_typeof(node) = 'object' THEN
    SELECT COALESCE(jsonb_object_agg(key, pg_temp.oan_species_breed_first(value)), '{}'::jsonb)
      INTO result FROM jsonb_each(node);
    IF node->>'widget-id' = 'ls_animal_details_table' AND jsonb_typeof(node->'widget-data-columns') = 'array' THEN
      SELECT jsonb_agg(value ORDER BY
               CASE value->>'column-key' WHEN 'species' THEN 0 WHEN 'breed' THEN 1 ELSE 2 END, position)
        INTO cols
        FROM jsonb_array_elements(result->'widget-data-columns') WITH ORDINALITY AS item(value, position);
      result := jsonb_set(result, '{widget-data-columns}', cols);
    END IF;
  ELSE
    result := node;
  END IF;
  RETURN result;
END $$;

UPDATE g2p_register_sections
SET section_ui_schema = pg_temp.oan_species_breed_first(section_ui_schema)
WHERE section_id = 'livestock_animal_details_section_01'
  AND section_ui_schema::text LIKE '%"ls_animal_details_table"%';
