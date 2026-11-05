-- The Livestock Details and Vital Event dialogs follow the animal's species, as
-- they did before the lists moved to Master Data:
--
--   Species  Donkey / horse / mule / pig ... are offered; EQUINES and OTHER are
--            kept for older records but not offered for new ones.
--   Breed    only the breeds of the chosen species (LIVESTOCK_BREED "species"
--            attribute); Improved / Local / Hybrid only for a species with none.
--   Sex      Male and Female; Mixed / Not Applicable as well for a species
--            without an ear tag (LIVESTOCK_SPECIES requires_ear_tag = false).
--            Castrated male and Female neuter stay in Master Data, not offered.
--   Ear tag, secondary identifier, head count, date of birth
--            shown and required by the species' Master Data settings: an
--            ear-tagged animal has an ear tag and a date of birth; a species
--            without an ear tag has a secondary identifier; a flock (poultry,
--            beehive) has a head count, and its date of birth is optional.
--
-- The platform's show / require rules compare one value per rule, and the last
-- rule wins, so they cannot test "species is one of ...". The species dropdown
-- (the filtered select of ui/staff-ui/overrides, registered as "select" so the
-- table still shows labels) therefore copies the species'
-- requires_ear_tag and is_flock_species into a hidden column, species_rules
-- ("requires_ear_tag=true is_flock_species=false"), and the fields' rules test
-- that column with "contains". A rule only adds a requirement when its setting
-- is present, so a stored row (no species_rules) is not asked for more than the
-- server's own species rules require.
--
-- Only the named columns of the two tables change, found by widget-id and
-- column-key; every other key on them is kept, and species_rules is added once.
-- Idempotent. Sorts after the field order patch and before
-- zzzzzzzzzz_required_animal_row.sql, which must stay the last file touching
-- the animal section.
CREATE OR REPLACE FUNCTION pg_temp.oan_species_columns(node jsonb, table_id text, patches jsonb, extra jsonb)
RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE result jsonb; cols jsonb; add jsonb;
BEGIN
  IF jsonb_typeof(node) = 'array' THEN
    SELECT COALESCE(jsonb_agg(pg_temp.oan_species_columns(value, table_id, patches, extra) ORDER BY position), '[]'::jsonb)
      INTO result FROM jsonb_array_elements(node) WITH ORDINALITY AS item(value, position);
  ELSIF jsonb_typeof(node) = 'object' THEN
    SELECT COALESCE(jsonb_object_agg(key, pg_temp.oan_species_columns(value, table_id, patches, extra)), '{}'::jsonb)
      INTO result FROM jsonb_each(node);
    IF node->>'widget-id' = table_id AND jsonb_typeof(node->'widget-data-columns') = 'array' THEN
      SELECT jsonb_agg(
               CASE WHEN patches ? (value->>'column-key') THEN
                 (value || ((patches->(value->>'column-key')) - 'widget-data-options'))
                 || CASE WHEN (patches->(value->>'column-key')) ? 'widget-data-options' THEN
                      jsonb_build_object('widget-data-options',
                        COALESCE(value->'widget-data-options', '{}'::jsonb)
                        || (patches->(value->>'column-key')->'widget-data-options'))
                    ELSE '{}'::jsonb END
               ELSE value END
               ORDER BY position)
        INTO cols
        FROM jsonb_array_elements(result->'widget-data-columns') WITH ORDINALITY AS item(value, position);
      SELECT COALESCE(jsonb_agg(e), '[]'::jsonb) INTO add
        FROM jsonb_array_elements(extra) e
       WHERE NOT EXISTS (SELECT 1 FROM jsonb_array_elements(cols) c WHERE c->>'column-key' = e->>'column-key');
      result := jsonb_set(result, '{widget-data-columns}', cols || add);
    END IF;
  ELSE
    result := node;
  END IF;
  RETURN result;
END $$;

UPDATE g2p_register_sections
SET section_ui_schema = pg_temp.oan_species_columns(section_ui_schema::jsonb, 'ls_animal_details_table', '{
  "species": {"widget": "select", "widget-hide-values": ["EQUINES", "OTHER"],
              "widget-copy-attributes": {"column": "species_rules", "attributes": ["requires_ear_tag", "is_flock_species"]}},
  "breed": {"widget": "select",
            "widget-filter-by": {"field": "species", "attribute": "species", "fallback": "unattributed"}},
  "gender": {"widget": "select",
             "widget-options-by": {"field": "species", "list": "LIVESTOCK_SPECIES", "attribute": "requires_ear_tag",
                                   "values": {"true": ["SEX_MALE", "SEX_FEMALE"],
                                              "false": ["SEX_MALE", "SEX_FEMALE", "SEX_MIXED"]},
                                   "default": ["SEX_MALE", "SEX_FEMALE"]}},
  "ear_tag_id": {"widget-required": false, "widget-data-options": {"actions": [
    {"action": "hide", "condition": {"field": "species_rules", "operator": "contains", "value": "requires_ear_tag=false"}},
    {"action": "require", "condition": {"field": "species_rules", "operator": "contains", "value": "requires_ear_tag=true"}}]}},
  "secondary_identifier": {"widget-required": false, "widget-data-options": {"actions": [
    {"action": "show", "condition": {"field": "species_rules", "operator": "contains", "value": "requires_ear_tag=false"}},
    {"action": "require", "condition": {"field": "species_rules", "operator": "contains", "value": "requires_ear_tag=false"}}]}},
  "quantity": {"widget-required": false, "widget-data-options": {"actions": [
    {"action": "show", "condition": {"field": "species_rules", "operator": "contains", "value": "is_flock_species=true"}},
    {"action": "require", "condition": {"field": "species_rules", "operator": "contains", "value": "is_flock_species=true"}}]}},
  "date_of_birth": {"widget-required": false, "widget-data-options": {"actions": [
    {"action": "require", "condition": {"field": "species_rules", "operator": "contains", "value": "is_flock_species=false"}}]}}
}'::jsonb, '[
  {"widget": "text", "column-key": "species_rules", "widget-type": "input", "widget-label": "Species rules",
   "widget-readonly": true, "widget-required": false, "column-visible-in-table": false,
   "widget-data-options": {"actions": [
     {"action": "hide", "condition": {"field": "species_rules", "operator": "notEquals", "value": "__shown_never__"}}]}}
]'::jsonb)
WHERE section_id = 'livestock_animal_details_section_01'
  AND section_ui_schema::text LIKE '%"ls_animal_details_table"%';

UPDATE g2p_register_sections
SET section_ui_schema = pg_temp.oan_species_columns(section_ui_schema::jsonb, 'ls_vital_event_details_table', '{
  "offspring_gender": {"widget": "select",
                       "widget-options-by": {"default": ["SEX_MALE", "SEX_FEMALE", "SEX_MIXED"]}},
  "offspring_breed": {"widget": "select",
                      "widget-filter-by": {"field": "species", "attribute": "species", "fallback": "unattributed"}}
}'::jsonb, '[]'::jsonb)
WHERE section_id = 'livestock_vital_event_details_section_01'
  AND section_ui_schema::text LIKE '%"ls_vital_event_details_table"%';

-- The vaccine column used the name oan-vaccine-select; as "select" its table cells show the
-- vaccine's name instead of its code, with the same species filter.
UPDATE g2p_register_sections
SET section_ui_schema = pg_temp.oan_species_columns(section_ui_schema::jsonb, 'ls_vaccination_details_table', '{
  "vaccine_type": {"widget": "select"}
}'::jsonb, '[]'::jsonb)
WHERE section_id = 'livestock_vaccination_details_section_01'
  AND section_ui_schema::text LIKE '%"ls_vaccination_details_table"%';
