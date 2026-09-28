-- Sections shown on the livestock intake form, in order.
--
-- Import Batch Details and Audit Log Details are deliberately absent: both are
-- system-generated (import batches come from bulk ingestion, audit rows are
-- written by the platform), so there is nothing for an operator to fill in at
-- registration. They remain on the register's "Imports & Audit" tab, which is
-- where they are read.
-- intake_tab_section_3 (Farmer Details — the read-only farmer profile card
-- keyed off the livestock record's own farmer_id/fayda_fan_id/farmer_name,
-- schema 997676d3-...) was removed on purpose: it is not required for
-- submission (section-required-for-submit: false in its section_ui_schema)
-- and on this form it only re-displays fields the operator just entered in
-- the Farmer section above, under a confusingly identical title. It stays on
-- the register's "Livestock" tab (g2p_register_ui_tab_sections.sql), where it
-- is the useful case — showing which farmer an already-registered livestock
-- record belongs to when nothing above it captured that already.
INSERT INTO "public"."g2p_intake_form_ui_tab_sections" ("tab_section_id","tab_id","section_id","section_order") VALUES
('intake_tab_section_1','0ebdc221-187d-5df6-9dc3-c6f4c4ee160e','livestock_farmer_identity_section_01',10),
('intake_tab_section_4','0ebdc221-187d-5df6-9dc3-c6f4c4ee160e','livestock_survey_personnel_section_02',40),
('intake_tab_section_5','0ebdc221-187d-5df6-9dc3-c6f4c4ee160e','livestock_livestock_location_section_03',50),
('intake_tab_section_6','0ebdc221-187d-5df6-9dc3-c6f4c4ee160e','livestock_animal_details_section_01',60),
('intake_tab_section_7','0ebdc221-187d-5df6-9dc3-c6f4c4ee160e','livestock_health_event_details_section_01',70),
('intake_tab_section_8','0ebdc221-187d-5df6-9dc3-c6f4c4ee160e','livestock_vaccination_details_section_01',80),
('intake_tab_section_9','0ebdc221-187d-5df6-9dc3-c6f4c4ee160e','livestock_vital_event_details_section_01',90),
('intake_tab_section_10','0ebdc221-187d-5df6-9dc3-c6f4c4ee160e','livestock_breeding_details_section_01',100);
-- intake_tab_section_11 (Vaccine Schedule Details) was removed on purpose —
-- see the matching comment in g2p_register_ui_tab_sections.sql.
