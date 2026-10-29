-- Readable text: nothing staff read in the Livestock registry is a code.
-- Dropdown options that showed a stored code as their label (HEALTHY,
-- UP_TO_DATE, NONE, MALE, YES ...) show plain words, date placeholders and
-- the ear tag placeholder are sentences, and validation messages that named
-- a field by its key now name it the way the form does.
--
-- Only display text changes. Option values (the stored codes), widget ids,
-- column keys and translation keys are untouched, and only the named keys of
-- a widget are rewritten, so the layout and required-field overlays keep
-- working on the same section JSON. Every statement is idempotent, so a plain
-- upgrade applies it and a replay changes nothing. It sorts after
-- 30_label_casing.sql, 40_farmer_tab_layout.sql and 45_required_fields.sql.

-- 1. Display text for the codes used as option labels (English). Translation
--    keys stay the codes; the values are what staff read.
UPDATE "public"."registry_languages"
SET "domain_translation" = (COALESCE("domain_translation"::jsonb, '{}'::jsonb) ||
'{
 "HEALTHY": "Healthy",
 "SICK": "Sick",
 "QUARANTINED": "Quarantined",
 "DECEASED": "Deceased",
 "UP_TO_DATE": "Up to date",
 "OVERDUE": "Overdue",
 "NONE": "None",
 "UNKNOWN": "Unknown",
 "MALE": "Male",
 "FEMALE": "Female",
 "OTHER": "Other",
 "YES": "Yes",
 "NO": "No",
 "HOME": "Home",
 "VETERINARY": "Veterinary",
 "MARKET": "Market",
 "FIELD": "Field",
 "QUARANTINE_CENTER": "Quarantine center",
 "BIRTH": "Birth",
 "MORTALITY": "Mortality",
 "DISEASE": "Disease",
 "INJURY": "Injury",
 "TREATMENT": "Treatment",
 "RECOVERY": "Recovery",
 "ACCIDENT": "Accident",
 "PREDATION": "Predation",
 "SLAUGHTER": "Slaughter",
 "NATURAL": "Natural",
 "PENDING": "Pending",
 "PROCESSING": "Processing",
 "COMPLETED": "Completed",
 "SUCCESSFUL": "Successful",
 "FAILED": "Failed",
 "CREATE": "Create",
 "UPDATE": "Update",
 "DELETE": "Delete",
 "IMPORT": "Import",
 "SYNC": "Sync",
 "MANUAL": "Manual",
 "CASE_BOOK": "Case book",
 "DOVAR": "Dovar",
 "LITS": "Lits",
 "ALIVE": "Alive",
 "coss_input_date_onset_min": "Date of onset: the date is before 1900. Enter a date on or after 1900-01-01.",
 "coss_input_date_resolution_min": "Date of resolution: the date is before 1900. Enter a date on or after 1900-01-01.",
 "coss_input_first_name_amh": "First name in Amharic: use 1-100 Ethiopic letters, spaces, hyphens or apostrophes. Remove digits and other symbols.",
 "coss_input_middle_name_amh": "Middle name in Amharic: use 1-100 Ethiopic letters, spaces, hyphens or apostrophes. Remove digits and other symbols.",
 "coss_input_last_name_amh": "Last name in Amharic: use 1-100 Ethiopic letters, spaces, hyphens or apostrophes. Remove digits and other symbols.",
 "coss_input_first_name_other": "First name in the other language: use 1-100 letters, spaces, hyphens or apostrophes. Remove digits and other symbols.",
 "coss_input_middle_name_other": "Middle name in the other language: use 1-100 letters, spaces, hyphens or apostrophes. Remove digits and other symbols.",
 "coss_input_last_name_other": "Last name in the other language: use 1-100 letters, spaces, hyphens or apostrophes. Remove digits and other symbols."
}'::jsonb)::json
WHERE "language_code" = 'en';

-- 2. Section JSON: rewrite only (a) dropdown options (label and value) whose label is a
--    code, (b) the placeholders and the date-order message
--    named below. Everything else in the JSON is copied through unchanged.
CREATE OR REPLACE FUNCTION pg_temp.readable_text(node jsonb)
RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE
 result jsonb;
 labels constant jsonb := '{
  "HEALTHY": "Healthy", "SICK": "Sick", "QUARANTINED": "Quarantined", "DECEASED": "Deceased",
  "UP_TO_DATE": "Up to date", "OVERDUE": "Overdue", "NONE": "None", "UNKNOWN": "Unknown",
  "MALE": "Male", "FEMALE": "Female", "OTHER": "Other", "YES": "Yes", "NO": "No",
  "HOME": "Home", "VETERINARY": "Veterinary", "MARKET": "Market", "FIELD": "Field",
  "QUARANTINE_CENTER": "Quarantine center", "BIRTH": "Birth", "MORTALITY": "Mortality",
  "DISEASE": "Disease", "INJURY": "Injury", "TREATMENT": "Treatment", "RECOVERY": "Recovery",
  "ACCIDENT": "Accident", "PREDATION": "Predation", "SLAUGHTER": "Slaughter",
  "NATURAL": "Natural", "PENDING": "Pending", "PROCESSING": "Processing",
  "COMPLETED": "Completed", "SUCCESSFUL": "Successful", "FAILED": "Failed",
  "CREATE": "Create", "UPDATE": "Update", "DELETE": "Delete", "IMPORT": "Import",
  "SYNC": "Sync", "MANUAL": "Manual", "CASE_BOOK": "Case book",
  "DOVAR": "Dovar", "LITS": "Lits", "ALIVE": "Alive"
 }';
 placeholders constant jsonb := '{
  "dd_mm_yyyy": "DD/MM/YYYY",
  "ET + 10 digits, e.g. ET0000000123": "ET followed by 10 digits, for example ET0000000123",
  "Flock / Batch / Hive ID (e.g. FLOCK-2026-01)": "Flock, batch or hive ID, for example FLOCK-2026-01"
 }';
 key text;
BEGIN
 IF jsonb_typeof(node) = 'array' THEN
  SELECT COALESCE(jsonb_agg(pg_temp.readable_text(value) ORDER BY ord), '[]'::jsonb) INTO result
   FROM jsonb_array_elements(node) WITH ORDINALITY a(value, ord);
 ELSIF jsonb_typeof(node) = 'object' THEN
  SELECT COALESCE(jsonb_object_agg(k, pg_temp.readable_text(v)), '{}'::jsonb) INTO result FROM jsonb_each(node) e(k, v);
  IF jsonb_typeof(node->'label') = 'string' AND node ? 'value' AND labels ? (node->>'label') THEN
   result := jsonb_set(result, '{label}', to_jsonb(labels->>(node->>'label')));
  END IF;
  FOREACH key IN ARRAY ARRAY['widget-data-placeholder', 'widget-placeholder'] LOOP
   IF jsonb_typeof(node->key) = 'string' AND placeholders ? (node->>key) THEN
    result := jsonb_set(result, ARRAY[key], to_jsonb(placeholders->>(node->>key)));
   END IF;
  END LOOP;
  IF jsonb_typeof(node->'notBeforeFieldMessage') = 'string'
     AND lower(node->>'notBeforeFieldMessage') = 'date of resolution cannot be before date of onset' THEN
   result := jsonb_set(result, '{notBeforeFieldMessage}', '"Date of resolution cannot be before date of onset"'::jsonb);
  END IF;
 ELSE
  result := node;
 END IF;
 RETURN result;
END $$;

UPDATE "public"."g2p_register_sections"
SET "section_ui_schema" = pg_temp.readable_text("section_ui_schema"::jsonb)
WHERE "section_ui_schema" IS NOT NULL
  AND "section_id" LIKE 'livestock\_%'
  AND "section_ui_schema"::jsonb IS DISTINCT FROM pg_temp.readable_text("section_ui_schema"::jsonb);
