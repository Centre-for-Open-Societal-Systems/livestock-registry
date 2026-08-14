-- Livestock Registry — sample farmers and livestock holdings (local / demo only).
--
-- The platform db-seed's load_sample_data.py is shaped for the reference
-- (farmer) registry, so LOAD_SAMPLE_DATA stays false for this variant and this
-- sample set is applied explicitly instead (see docker-compose.yml).
--
-- The Farmer Registry is the system of record for people: each livestock holding
-- carries the farmer's ids and name and mirrors the Fayda FAN into
-- link_foundational_id. The Farmer rows here exist so the Farmer tab has
-- something to show and the ids line up.
--
-- Farmer IDs follow the FR- + 10 digits format the livestock module validates.
-- OAN IDs follow <farmer code>-<FIRST NAME>-<###>, as _generate_oan_id builds them.

INSERT INTO "public"."g2p_register_farmers" (
    "internal_record_id","functional_record_id","link_internal_record_id","link_foundational_id",
    "record_name","record_image_document_id","created_by","created_at","last_approved_at",
    "last_approved_by","search_text","record_status","record_status_reason",
    "farmer_id","fayda_fan_id","farmer_name","first_name","middle_name","last_name",
    "gender","date_of_birth","mobile_number","registration_date","status",
    "latitude","longitude","address_line_1","address_line_2","country_code"
) VALUES
('farmer0001','FR-1234567890',NULL,'1234567890','Abebe Kebede',NULL,'seeder','2026-04-01 00:00:00','2026-04-01 00:00:00','seeder','FR-1234567890 FR-1234567890 1234567890 Abebe Kebede Abebe Kebede +251911000101 VERIFIED Kebele 01 Gote 3 ETH','ACTIVE',NULL,'FR-1234567890','1234567890','Abebe Kebede','Abebe','Kebede','Kebede','MALE','1984-03-12','+251911000101','2026-04-01','VERIFIED','9.0300','38.7400','Kebele 01','Gote 3','ETH'),
('farmer0002','FR-9876543210',NULL,'9876543210','Almaz Tadesse',NULL,'seeder','2026-04-01 00:00:00','2026-04-01 00:00:00','seeder','FR-9876543210 FR-9876543210 9876543210 Almaz Tadesse Almaz Tadesse +251911000102 VERIFIED Kebele 04 Gote 1 ETH','ACTIVE',NULL,'FR-9876543210','9876543210','Almaz Tadesse','Almaz','Tadesse','Tadesse','FEMALE','1991-11-05','+251911000102','2026-04-01','VERIFIED','8.5400','39.2700','Kebele 04','Gote 1','ETH')
ON CONFLICT ("internal_record_id") DO NOTHING;

INSERT INTO "public"."g2p_register_livestocks" (
    "internal_record_id","functional_record_id","link_internal_record_id","link_foundational_id",
    "record_name","record_image_document_id","created_by","created_at","last_approved_at",
    "last_approved_by","search_text","record_status","record_status_reason",
    "farmer_uuid","farmer_id","fayda_fan_id","farmer_name","oan_id","secondary_identifier",
    "registration_date","status","state","state_date","source_system","sync_status",
    "total_animals","notes","surveyor_name","surveyor_mobile_number",
    "supervisor_name","supervisor_mobile_number","latitude","longitude",
    "address_line_1","address_line_2","country_code"
) VALUES
('ls0001','LS-000000000001',NULL,'1234567890','Abebe Kebede FR-1234567890-ABEBE-001',NULL,'seeder','2026-04-01 00:00:00','2026-04-01 00:00:00','seeder','LS-000000000001 FR-1234567890-ABEBE-001 Abebe Kebede FR-1234567890 1234567890 VERIFIED VERIFIED MANUAL Chala Tesfaye Muluken Assefa Kebele 01 Gote 3 ETH','ACTIVE',NULL,'a0000000-0000-4000-8000-000000000001','FR-1234567890','1234567890','Abebe Kebede','FR-1234567890-ABEBE-001',NULL,'2026-04-01','VERIFIED','VERIFIED','2026-04-01','MANUAL','SYNCED',3,'Mixed cattle and small ruminant holding.','Chala Tesfaye','+251911000001','Muluken Assefa','+251911000002','9.0300','38.7400','Kebele 01','Gote 3','ETH'),
('ls0002','LS-000000000002',NULL,'9876543210','Almaz Tadesse FR-9876543210-ALMAZ-001',NULL,'seeder','2026-04-01 00:00:00','2026-04-01 00:00:00','seeder','LS-000000000002 FR-9876543210-ALMAZ-001 Almaz Tadesse FR-9876543210 9876543210 WOREDA_APPROVED WOREDA_APPROVED LITS Chala Tesfaye Muluken Assefa Kebele 04 Gote 1 ETH','ACTIVE',NULL,'a0000000-0000-4000-8000-000000000002','FR-9876543210','9876543210','Almaz Tadesse','FR-9876543210-ALMAZ-001',NULL,'2026-04-05','WOREDA_APPROVED','WOREDA_APPROVED','2026-04-20','LITS','SYNCED',2,'Dairy cross and poultry holding.','Chala Tesfaye','+251911000001','Muluken Assefa','+251911000002','8.5400','39.2700','Kebele 04','Gote 1','ETH')
ON CONFLICT ("internal_record_id") DO NOTHING;
