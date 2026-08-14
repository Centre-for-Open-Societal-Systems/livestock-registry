-- Livestock Registry — the animal and event lines for the holdings seeded in
-- 10_farmers_livestock.sql. Every line links straight to its livestock holding
-- (link_internal_record_id) and names its animal by ear tag, mirroring how the
-- livestock module's one2many lines hang off g2p.livestock.registry.

INSERT INTO "public"."g2p_register_animals" (
    "internal_record_id","functional_record_id","link_internal_record_id","link_foundational_id",
    "record_name","record_image_document_id","created_by","created_at","last_approved_at",
    "last_approved_by","search_text","record_status","record_status_reason",
    "ear_tag_id","secondary_identifier","animal_name","species","breed","gender",
    "date_of_birth","age","weight","health_status","vaccination_status",
    "registration_date","state"
) VALUES
('animal0001','AN-000000000001','ls0001',NULL,'ET-OR-0000001 CATTLE',NULL,'seeder','2026-04-01 00:00:00','2026-04-01 00:00:00','seeder','AN-000000000001 ET-OR-0000001 Bora CATTLE BORAN FEMALE HEALTHY UP_TO_DATE CONFIRMED','ACTIVE',NULL,'ET-OR-0000001',NULL,'Bora','CATTLE','BORAN','FEMALE','2021-05-14','5y',320.0,'HEALTHY','UP_TO_DATE','2026-04-01','CONFIRMED'),
('animal0002','AN-000000000002','ls0001',NULL,'ET-OR-0000002 CATTLE',NULL,'seeder','2026-04-01 00:00:00','2026-04-01 00:00:00','seeder','AN-000000000002 ET-OR-0000002 Gudina CATTLE BORAN MALE HEALTHY UP_TO_DATE CONFIRMED','ACTIVE',NULL,'ET-OR-0000002',NULL,'Gudina','CATTLE','BORAN','MALE','2022-09-02','3y',410.0,'HEALTHY','UP_TO_DATE','2026-04-01','CONFIRMED'),
('animal0003','AN-000000000003','ls0001',NULL,'ET-OR-0000003 SHEEP',NULL,'seeder','2026-04-01 00:00:00','2026-04-01 00:00:00','seeder','AN-000000000003 ET-OR-0000003 SHEEP MENZ FEMALE SICK OVERDUE CONFIRMED','ACTIVE',NULL,'ET-OR-0000003',NULL,NULL,'SHEEP','MENZ','FEMALE','2024-02-20','2y',28.5,'SICK','OVERDUE','2026-04-01','CONFIRMED'),
('animal0004','AN-000000000004','ls0002',NULL,'ET-AM-0000011 CATTLE',NULL,'seeder','2026-04-05 00:00:00','2026-04-05 00:00:00','seeder','AN-000000000004 ET-AM-0000011 Lucy CATTLE HOLSTEIN_CROSS FEMALE HEALTHY UP_TO_DATE CONFIRMED','ACTIVE',NULL,'ET-AM-0000011',NULL,'Lucy','CATTLE','HOLSTEIN_CROSS','FEMALE','2022-01-30','4y',465.0,'HEALTHY','UP_TO_DATE','2026-04-05','CONFIRMED'),
('animal0005','AN-000000000005','ls0002',NULL,'ET-AM-0000012 POULTRY',NULL,'seeder','2026-04-05 00:00:00','2026-04-05 00:00:00','seeder','AN-000000000005 ET-AM-0000012 POULTRY BOVANS_BROWN FEMALE HEALTHY NONE DRAFT','ACTIVE',NULL,'ET-AM-0000012',NULL,NULL,'POULTRY','BOVANS_BROWN','FEMALE','2025-08-11','1y',1.9,'HEALTHY','NONE','2026-04-05','DRAFT')
ON CONFLICT ("internal_record_id") DO NOTHING;

INSERT INTO "public"."g2p_register_health_events" (
    "internal_record_id","functional_record_id","link_internal_record_id","link_foundational_id",
    "record_name","record_image_document_id","created_by","created_at","last_approved_at",
    "last_approved_by","search_text","record_status","record_status_reason",
    "ear_tag_id","species","event_type","disease_type","date_onset","date_resolution",
    "treatment","veterinarian_name","location","location_details","is_notifiable","notes"
) VALUES
('health0001','HE-000000000001','ls0001',NULL,'DISEASE ET-OR-0000003',NULL,'seeder','2026-05-02 00:00:00','2026-05-02 00:00:00','seeder','HE-000000000001 ET-OR-0000003 SHEEP DISEASE INTERNAL_PARASITES Albendazole drench Dr Hailu Bekele VETERINARY','ACTIVE',NULL,'ET-OR-0000003','SHEEP','DISEASE','INTERNAL_PARASITES','2026-05-02',NULL,'Albendazole drench','Dr Hailu Bekele','VETERINARY','Woreda veterinary clinic',FALSE,'Follow-up in two weeks.'),
('health0002','HE-000000000002','ls0001',NULL,'TREATMENT ET-OR-0000001',NULL,'seeder','2026-04-18 00:00:00','2026-04-18 00:00:00','seeder','HE-000000000002 ET-OR-0000001 CATTLE TREATMENT EXTERNAL_PARASITES Acaricide spray Dr Hailu Bekele HOME','ACTIVE',NULL,'ET-OR-0000001','CATTLE','TREATMENT','EXTERNAL_PARASITES','2026-04-16','2026-04-18','Acaricide spray','Dr Hailu Bekele','HOME',NULL,FALSE,NULL),
('health0003','HE-000000000003','ls0002',NULL,'DISEASE ET-AM-0000011',NULL,'seeder','2026-06-11 00:00:00','2026-06-11 00:00:00','seeder','HE-000000000003 ET-AM-0000011 CATTLE DISEASE MASTITIS Intramammary antibiotic Dr Sara Girma FIELD','ACTIVE',NULL,'ET-AM-0000011','CATTLE','DISEASE','MASTITIS','2026-06-08','2026-06-11','Intramammary antibiotic course','Dr Sara Girma','FIELD',NULL,FALSE,'Milk withheld for 5 days.')
ON CONFLICT ("internal_record_id") DO NOTHING;

INSERT INTO "public"."g2p_register_vaccinations" (
    "internal_record_id","functional_record_id","link_internal_record_id","link_foundational_id",
    "record_name","record_image_document_id","created_by","created_at","last_approved_at",
    "last_approved_by","search_text","record_status","record_status_reason",
    "ear_tag_id","species","vaccine_type","vaccination_date","next_due_date",
    "batch_number","administered_by","notes"
) VALUES
('vacc0001','VC-000000000001','ls0001',NULL,'ANTHRAX_CATTLE ET-OR-0000001',NULL,'seeder','2026-04-10 00:00:00','2026-04-10 00:00:00','seeder','VC-000000000001 ET-OR-0000001 CATTLE ANTHRAX_CATTLE NVI-2026-0431 Dr Hailu Bekele','ACTIVE',NULL,'ET-OR-0000001','CATTLE','ANTHRAX_CATTLE','2026-04-10','2027-04-10','NVI-2026-0431','Dr Hailu Bekele',NULL),
('vacc0002','VC-000000000002','ls0001',NULL,'BLACKLEG ET-OR-0000002',NULL,'seeder','2026-04-10 00:00:00','2026-04-10 00:00:00','seeder','VC-000000000002 ET-OR-0000002 CATTLE BLACKLEG NVI-2026-0432 Dr Hailu Bekele','ACTIVE',NULL,'ET-OR-0000002','CATTLE','BLACKLEG','2026-04-10','2027-04-10','NVI-2026-0432','Dr Hailu Bekele',NULL),
('vacc0003','VC-000000000003','ls0001',NULL,'PPR_SHEEP ET-OR-0000003',NULL,'seeder','2025-04-12 00:00:00','2025-04-12 00:00:00','seeder','VC-000000000003 ET-OR-0000003 SHEEP PPR_SHEEP NVI-2025-0119 Dr Hailu Bekele','ACTIVE',NULL,'ET-OR-0000003','SHEEP','PPR_SHEEP','2025-04-12','2026-04-12','NVI-2025-0119','Dr Hailu Bekele','Overdue — flagged for the next campaign.'),
('vacc0004','VC-000000000004','ls0002',NULL,'LSD ET-AM-0000011',NULL,'seeder','2026-05-03 00:00:00','2026-05-03 00:00:00','seeder','VC-000000000004 ET-AM-0000011 CATTLE LSD NVI-2026-0555 Dr Sara Girma','ACTIVE',NULL,'ET-AM-0000011','CATTLE','LSD','2026-05-03','2027-05-03','NVI-2026-0555','Dr Sara Girma',NULL)
ON CONFLICT ("internal_record_id") DO NOTHING;

INSERT INTO "public"."g2p_register_vital_events" (
    "internal_record_id","functional_record_id","link_internal_record_id","link_foundational_id",
    "record_name","record_image_document_id","created_by","created_at","last_approved_at",
    "last_approved_by","search_text","record_status","record_status_reason",
    "ear_tag_id","species","event_type","event_date","cause","location","location_details",
    "disease_type","date_onset","date_resolution","treatment","veterinarian_name",
    "is_notifiable","offspring_count","offspring_ear_tag_prefix","reporting_officer","notes"
) VALUES
('vital0001','VE-000000000001','ls0001',NULL,'BIRTH ET-OR-0000001',NULL,'seeder','2026-06-20 00:00:00','2026-06-20 00:00:00','seeder','VE-000000000001 ET-OR-0000001 CATTLE BIRTH HOME Chala Tesfaye','ACTIVE',NULL,'ET-OR-0000001','CATTLE','BIRTH','2026-06-20',NULL,'HOME',NULL,NULL,NULL,NULL,NULL,NULL,FALSE,1,'ET-OR-00000','Chala Tesfaye','Single healthy calf.'),
('vital0002','VE-000000000002','ls0002',NULL,'MORTALITY ET-AM-0000012',NULL,'seeder','2026-07-02 00:00:00','2026-07-02 00:00:00','seeder','VE-000000000002 ET-AM-0000012 POULTRY MORTALITY PREDATION FIELD Chala Tesfaye','ACTIVE',NULL,'ET-AM-0000012','POULTRY','MORTALITY','2026-07-02','PREDATION','FIELD','Open run behind the homestead',NULL,NULL,NULL,NULL,NULL,FALSE,0,NULL,'Chala Tesfaye',NULL)
ON CONFLICT ("internal_record_id") DO NOTHING;

INSERT INTO "public"."g2p_register_breedings" (
    "internal_record_id","functional_record_id","link_internal_record_id","link_foundational_id",
    "record_name","record_image_document_id","created_by","created_at","last_approved_at",
    "last_approved_by","search_text","record_status","record_status_reason",
    "ear_tag_id","species","event_type","breeding_date","sire_or_semen_id","location",
    "location_details","ai_technician_name","ai_technique","semen_batch_number",
    "expected_calving_date","pregnancy_confirmed","pregnancy_confirmation_date","outcome","notes"
) VALUES
('breed0001','BR-000000000001','ls0001',NULL,'NATURAL ET-OR-0000001',NULL,'seeder','2025-09-15 00:00:00','2025-09-15 00:00:00','seeder','BR-000000000001 ET-OR-0000001 CATTLE NATURAL ET-OR-0000002 HOME SUCCESSFUL','ACTIVE',NULL,'ET-OR-0000001','CATTLE','NATURAL','2025-09-15','ET-OR-0000002','HOME',NULL,NULL,NULL,NULL,'2026-06-22',TRUE,'2025-11-20','SUCCESSFUL','Calved on 2026-06-20.'),
('breed0002','BR-000000000002','ls0002',NULL,'AI ET-AM-0000011',NULL,'seeder','2026-07-10 00:00:00','2026-07-10 00:00:00','seeder','BR-000000000002 ET-AM-0000011 CATTLE AI HF-SEMEN-2026-77 VETERINARY Tsegaye Alemu PENDING','ACTIVE',NULL,'ET-AM-0000011','CATTLE','AI','2026-07-10','HF-SEMEN-2026-77','VETERINARY','Woreda AI centre','Tsegaye Alemu','Rectovaginal','HF-2026-77','2027-04-17',FALSE,NULL,'PENDING',NULL)
ON CONFLICT ("internal_record_id") DO NOTHING;

INSERT INTO "public"."g2p_register_vaccine_schedules" (
    "internal_record_id","functional_record_id","link_internal_record_id","link_foundational_id",
    "record_name","record_image_document_id","created_by","created_at","last_approved_at",
    "last_approved_by","search_text","record_status","record_status_reason",
    "vaccine_name","species","interval_days","is_active","notes"
) VALUES
('vsched0001','VS-000000000001','ls0001',NULL,'ANTHRAX_CATTLE CATTLE',NULL,'seeder','2026-04-01 00:00:00','2026-04-01 00:00:00','seeder','VS-000000000001 ANTHRAX_CATTLE CATTLE','ACTIVE',NULL,'ANTHRAX_CATTLE','CATTLE',365,TRUE,'Annual, ahead of the rainy season.'),
('vsched0002','VS-000000000002','ls0001',NULL,'BLACKLEG CATTLE',NULL,'seeder','2026-04-01 00:00:00','2026-04-01 00:00:00','seeder','VS-000000000002 BLACKLEG CATTLE','ACTIVE',NULL,'BLACKLEG','CATTLE',365,TRUE,NULL),
('vsched0003','VS-000000000003','ls0001',NULL,'PPR_SHEEP SHEEP',NULL,'seeder','2026-04-01 00:00:00','2026-04-01 00:00:00','seeder','VS-000000000003 PPR_SHEEP SHEEP','ACTIVE',NULL,'PPR_SHEEP','SHEEP',365,TRUE,NULL),
('vsched0004','VS-000000000004','ls0002',NULL,'NEWCASTLE POULTRY',NULL,'seeder','2026-04-05 00:00:00','2026-04-05 00:00:00','seeder','VS-000000000004 NEWCASTLE POULTRY','ACTIVE',NULL,'NEWCASTLE','POULTRY',90,TRUE,'Quarterly for backyard flocks.')
ON CONFLICT ("internal_record_id") DO NOTHING;

INSERT INTO "public"."g2p_register_import_batches" (
    "internal_record_id","functional_record_id","link_internal_record_id","link_foundational_id",
    "record_name","record_image_document_id","created_by","created_at","last_approved_at",
    "last_approved_by","search_text","record_status","record_status_reason",
    "batch_reference","source_system","state","import_filename","import_file_document_id",
    "total_rows","success_count","failure_count","conflict_count","error_log",
    "processed_by","processing_date"
) VALUES
('batch0001','IB-000000000001','ls0002',NULL,'LITS-2026-04-05 LITS',NULL,'seeder','2026-04-05 00:00:00','2026-04-05 00:00:00','seeder','IB-000000000001 LITS-2026-04-05 LITS COMPLETED lits_export_20260405.csv seeder','ACTIVE',NULL,'LITS-2026-04-05','LITS','COMPLETED','lits_export_20260405.csv',NULL,2,2,0,0,NULL,'seeder','2026-04-05 09:15:00')
ON CONFLICT ("internal_record_id") DO NOTHING;
