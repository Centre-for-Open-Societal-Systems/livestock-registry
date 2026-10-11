INSERT INTO "public"."data_models" ("data_model_id","data_model_mnemonic","pattern_for_data_model","response_template_document_id","is_active") VALUES
('c331ba96-ac35-4014-9d13-4ef327f6b79b','DCI','*','1f0953d4-f0fb-4336-a126-4d0519a74ffc','TRUE');

-- DCI response template: dci_commons_response.json.j2

-- Livestock ODK model: the envelope the ODK hooks (odk_ingest_hooks.py,
-- patched G2PIngestService.ingest_data) build around a connector submission:
--   {"body": {"header": {"sender_id": "Livestock", "message_id": <instanceID>,
--             "signature": ...}, "message": {"payload": <OData submission>}}}
-- The hooks call ingest_data with this mnemonic plus the livestock register and
-- intake form ids, so classification is skipped; the semantic pattern below is
-- what the transformation worker reads the business payload with. Same rows
-- as patch_livestock_odk_ingestion.sql (for environments seeded before this).
INSERT INTO "public"."data_models" ("data_model_id","data_model_mnemonic","pattern_for_data_model","response_template_document_id","is_active") VALUES
('d2c7a1e4-5f60-4b8a-9c3d-1e2f3a4b5c6d','LIVESTOCK_ODK_MODEL','$.body.header.sender_id=>^Livestock$','1f0953d4-f0fb-4336-a126-4d0519a74ffc','TRUE')
ON CONFLICT ("data_model_id") DO NOTHING;
