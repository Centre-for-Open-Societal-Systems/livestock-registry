-- Sections shown on the livestock intake form, in order.
--
-- Import Batch Details and Audit Log Details are deliberately absent: both are
-- system-generated (import batches come from bulk ingestion, audit rows are
-- written by the platform), so there is nothing for an operator to fill in at
-- registration. They remain on the register's "Imports & Audit" tab, which is
-- where they are read.
INSERT INTO "public"."g2p_intake_form_ui_tab_sections" ("tab_section_id","tab_id","section_id","section_order") VALUES
('intake_tab_section_1','0ebdc221-187d-5df6-9dc3-c6f4c4ee160e','livestock_farmer_identity_section_01',10),
('intake_tab_section_3','0ebdc221-187d-5df6-9dc3-c6f4c4ee160e','livestock_livestock_record_section_01',30),
('intake_tab_section_4','0ebdc221-187d-5df6-9dc3-c6f4c4ee160e','livestock_survey_personnel_section_02',40),
('intake_tab_section_5','0ebdc221-187d-5df6-9dc3-c6f4c4ee160e','livestock_livestock_location_section_03',50),
('intake_tab_section_6','0ebdc221-187d-5df6-9dc3-c6f4c4ee160e','livestock_animal_details_section_01',60),
('intake_tab_section_7','0ebdc221-187d-5df6-9dc3-c6f4c4ee160e','livestock_health_event_details_section_01',70),
('intake_tab_section_8','0ebdc221-187d-5df6-9dc3-c6f4c4ee160e','livestock_vaccination_details_section_01',80),
('intake_tab_section_9','0ebdc221-187d-5df6-9dc3-c6f4c4ee160e','livestock_vital_event_details_section_01',90),
('intake_tab_section_10','0ebdc221-187d-5df6-9dc3-c6f4c4ee160e','livestock_breeding_details_section_01',100),
('intake_tab_section_11','0ebdc221-187d-5df6-9dc3-c6f4c4ee160e','livestock_vaccine_schedule_details_section_01',110);
