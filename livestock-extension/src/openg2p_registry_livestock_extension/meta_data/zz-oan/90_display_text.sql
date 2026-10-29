-- Display text, second pass: what the Livestock audit still found after the
-- readable-text overlay. Only display text changes: ids, mnemonics, codes,
-- option values and translation keys stay as they are.
--
-- 1. Animal table, retagging and audit labels in sentence case, and the two
--    labels that named a field badly (Farmer link status, Record type).
-- 2. Messages: dates in the DD/MM/YYYY the form uses, the Fayda FAN and
--    veterinarian messages name the field as it is labelled, the retag date
--    message names Date of retagging.
-- 3. The first Livestock tab reads Livestock record, the intake tab is a key.
-- 4. Register descriptions and subjects in sentence case; register mnemonics,
--    list headers and status codes get display text through the domain
--    translations, which override the platform's Title Case list headers.
--
-- Explicit-id UPDATEs and named-key merges only, so a plain upgrade applies
-- them to long-lived databases and a replay changes nothing. Sorts after
-- 85_readable_text.sql.

-- 1. Section JSON: exact label pairs, every other key is copied through.
CREATE OR REPLACE FUNCTION pg_temp.display_text(t text)
RETURNS text LANGUAGE sql IMMUTABLE AS $$
 SELECT replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(t, '"widget-label": "Livestock Details"', '"widget-label": "Livestock details"'), '"widget-label": "Livestock Ear Tag"', '"widget-label": "Ear tag"'), '"widget-label": "Secondary Identifier"', '"widget-label": "Secondary identifier"'), '"widget-label": "Quantity (Head Count)"', '"widget-label": "Number of animals (head count)"'), '"widget-label": "Date of Birth"', '"widget-label": "Date of birth"'), '"widget-label": "Health Status"', '"widget-label": "Health status"'), '"widget-label": "Vaccination Status"', '"widget-label": "Vaccination status"'), '"widget-label": "Registration Date"', '"widget-label": "Registration date"'), '"widget-label": "Farmer reference"', '"widget-label": "Farmer link status"'), '"widget-label": "Related model"', '"widget-label": "Record type"'), '"section-title": "Livestock Details"', '"section-title": "Livestock details"'), '"widget-data-dialog-title-add": "Add Livestock Details"', '"widget-data-dialog-title-add": "Add livestock details"'), '"widget-data-dialog-title-edit": "Edit Livestock Details"', '"widget-data-dialog-title-edit": "Edit livestock details"'), '"label": "Mixed / Not Applicable"', '"label": "Mixed or not applicable"'), '"label": "Mixed / not applicable"', '"label": "Mixed or not applicable"')
$$;

UPDATE "public"."g2p_register_sections"
SET "section_ui_schema" = pg_temp.display_text("section_ui_schema"::jsonb::text)::jsonb
WHERE "section_ui_schema" IS NOT NULL
  AND "section_id" LIKE 'livestock\_%'
  AND pg_temp.display_text("section_ui_schema"::jsonb::text) <> "section_ui_schema"::jsonb::text;

UPDATE "public"."g2p_register_sections"
SET "section_description" = 'Livestock details'
WHERE "section_id" LIKE 'livestock\_%'
  AND "section_description" = 'Livestock Details';

UPDATE "public"."g2p_register_sections"
SET "section_ui_schema" = replace("section_ui_schema"::jsonb::text, '"section-title": "Farmer details"', '"section-title": "Farmer and holding"')::jsonb
WHERE "section_id" = 'livestock_livestock_record_section_01'
  AND "section_ui_schema"::jsonb::text LIKE '%"section-title": "Farmer details"%';

-- 3. The intake tab label is a translation key, as the register tabs are
--    (50_tab_label_keys.sql); the text comes from the domain translations below.
UPDATE "public"."g2p_intake_form_ui_tabs"
SET "tab_label" = 'livestock_intake_tab'
WHERE "tab_id" = '0ebdc221-187d-5df6-9dc3-c6f4c4ee160e'
  AND "tab_label" <> 'livestock_intake_tab';

-- 4. Register descriptions and subjects.
UPDATE "public"."g2p_register_definitions"
SET "register_description" = 'Farmer register'
WHERE "register_id" = 'f9c6a359-9563-5a43-b0fe-6c7e452037a3';

UPDATE "public"."g2p_register_definitions"
SET "register_description" = 'Livestock register', "register_subject" = 'Livestock records'
WHERE "register_id" = '997676d3-7008-59f9-b23e-613ad79bbb08';

UPDATE "public"."g2p_register_definitions"
SET "register_description" = 'Animals in a livestock record'
WHERE "register_id" = '041a9f79-2142-548a-a15b-a4c76fc9f6f7';

UPDATE "public"."g2p_register_definitions"
SET "register_description" = 'Health event register'
WHERE "register_id" = 'a40e4a02-1b82-5b31-89df-71624bd96545';

UPDATE "public"."g2p_register_definitions"
SET "register_description" = 'Vaccination register'
WHERE "register_id" = '51c1f6d6-856a-5e2f-84e9-ff5abdc4fb75';

UPDATE "public"."g2p_register_definitions"
SET "register_description" = 'Vital event register'
WHERE "register_id" = '76811bf6-07df-5ed4-9466-13b782f627fe';

UPDATE "public"."g2p_register_definitions"
SET "register_description" = 'Breeding register'
WHERE "register_id" = '192c08b0-5403-5167-968a-2676d4af2879';

UPDATE "public"."g2p_register_definitions"
SET "register_description" = 'Vaccine schedule register'
WHERE "register_id" = '5cdf80bf-0cdb-53e4-a4cf-71927f809250';

UPDATE "public"."g2p_register_definitions"
SET "register_description" = 'Audit log register'
WHERE "register_id" = '6a3699f0-4b17-5d0d-b8b3-4822bfdab7aa';

UPDATE "public"."g2p_register_definitions"
SET "register_description" = 'Ear tag replacement register'
WHERE "register_id" = 'b853f1db-6dd6-5b16-a0d8-25a8524142e6';

-- Display text (English). Named keys replace, every other key is kept.
UPDATE "public"."registry_languages"
SET "domain_translation" = (COALESCE("domain_translation"::jsonb, '{}'::jsonb) ||
'{
 "coss_input_applied_on_min": "Applied on: the date is before 1900. Enter a date on or after 01/01/1900.",
 "coss_input_breeding_date_min": "Breeding date: the date is before 1900. Enter a date on or after 01/01/1900.",
 "coss_input_date_of_birth_min": "Date of birth: the date is before 1900. Enter a date on or after 01/01/1900.",
 "coss_input_date_onset_min": "Date of onset: the date is before 1900. Enter a date on or after 01/01/1900.",
 "coss_input_date_resolution_min": "Date of resolution: the date is before 1900. Enter a date on or after 01/01/1900.",
 "coss_input_event_date_min": "Event date: the date is before 1900. Enter a date on or after 01/01/1900.",
 "coss_input_expected_calving_date_min": "Expected calving date: the date is before 1900. Enter a date on or after 01/01/1900.",
 "coss_input_next_due_date_min": "Next due date: the date is before 1900. Enter a date on or after 01/01/1900.",
 "coss_input_pregnancy_confirmation_date_min": "Pregnancy confirmation date: the date is before 1900. Enter a date on or after 01/01/1900.",
 "coss_input_registration_date_min": "Registration date: the date is before 1900. Enter a date on or after 01/01/1900.",
 "coss_input_retag_date_min": "Date of retagging: the date is before 1900. Enter a date on or after 01/01/1900.",
 "coss_input_state_date_min": "State date: the date is before 1900. Enter a date on or after 01/01/1900.",
 "coss_input_vaccination_date_min": "Vaccination date: the date is before 1900. Enter a date on or after 01/01/1900.",
 "coss_field_date_min": "{label}: the date is before 1900. Enter a date on or after 01/01/1900.",
 "coss_input_fayda_fan_id": "Fayda FAN: enter exactly 16 digits, spaces allowed. For a 12-digit FIN use the Fayda FIN field.",
 "coss_field_fan_format": "{label}: enter exactly 16 digits, spaces allowed. For a 12-digit FIN use the Fayda FIN field.",
 "coss_input_veterinarian_name": "Veterinarian: use 1-100 letters, spaces, hyphens or apostrophes.",
 "livestock_livestock_tab": "Livestock record",
 "ls_livestock_record": "Farmer and holding",
 "livestock_intake_tab": "Livestock intake",
 "Livestock Intake": "Livestock intake",
 "HealthEvent": "Health events",
 "VitalEvent": "Vital events",
 "VaccineSchedule": "Vaccine schedules",
 "Retagging": "Ear tag replacements",
 "AuditLog": "Audit logs",
 "ear_tag_id": "Ear tag",
 "farmer_name": "Farmer name",
 "health_status": "Health status",
 "vaccination_status": "Vaccination status",
 "secondary_identifier": "Secondary identifier",
 "total_animals": "Total livestock",
 "state": "Approval stage",
 "fayda_fan_id": "Fayda FAN (16 digits)",
 "APPROVED": "Approved",
 "REJECTED": "Rejected",
 "FINAL": "Submitted",
 "NOT_APPLICABLE": "Not applicable",
 "PROCESSED": "Processed",
 "ADD": "New",
 "FARMER_REFERENCE_CHANGED_V1": "Farmer reference changed",
 "INTAKE_FORM_PATTERN_NOT_MATCHED": "No intake form matches this message",
 "ls_farmer_identity": "Farmer identity",
 "Live_stock_partner_internal": "Livestock registry (internal)"
}'::jsonb)::json
WHERE "language_code" = 'en';
