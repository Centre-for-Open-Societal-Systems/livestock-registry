INSERT INTO "public"."incoming_model_semantic_patterns" (
    "semantic_pattern_id",
    "data_model_id",
    "register_id",
    "intake_form_id",
    "pattern_for_register",
    "pattern_for_intake_form",
    "key_path_for_business_payload",
    "raw_payload_enricher_class"
) VALUES (
    '5d1c7f43-2a6b-4d18-9c30-7f4b2e8a91cd',
    'c331ba96-ac35-4014-9d13-4ef327f6b79b',
    '997676d3-7008-59f9-b23e-613ad79bbb08',
    'e92e8be1-207f-518e-99c2-8bc21cc1f112',
    '$.body.message.search_response[0].data.reg_type=>^Livestock$',
    '$.body.message.search_response[0].data.reg_record_type=>^Livestock$',
    '$.body.message.search_response[0].data.reg_records[0]',
    'G2PDciLivestockCreateEnricherService'
)
ON CONFLICT DO NOTHING;

-- Livestock ODK model: the envelope the ODK hooks (odk_ingest_hooks.py,
-- patched G2PIngestService.ingest_data) build around a connector submission:
--   {"body": {"header": {"sender_id": "Livestock", "message_id": <instanceID>,
--             "signature": ...}, "message": {"payload": <OData submission>}}}
-- The hooks call ingest_data with this mnemonic plus the livestock register and
-- intake form ids, so classification is skipped; the semantic pattern below is
-- what the transformation worker reads the business payload with. Same rows
-- as patch_livestock_odk_ingestion.sql (for environments seeded before this).
INSERT INTO "public"."incoming_model_semantic_patterns" (
    "semantic_pattern_id","data_model_id","register_id","intake_form_id",
    "pattern_for_register","pattern_for_intake_form","key_path_for_business_payload","raw_payload_enricher_class"
) VALUES (
    '9e8d7c6b-5a4f-4e3d-9c2b-1a0f9e8d7c6b','d2c7a1e4-5f60-4b8a-9c3d-1e2f3a4b5c6d','997676d3-7008-59f9-b23e-613ad79bbb08','e92e8be1-207f-518e-99c2-8bc21cc1f112',
    '$.body.header.sender_id=>^Livestock$','$.body.header.sender_id=>^Livestock$',
    '$.body.message.payload','G2PDciLivestockCreateEnricherService'
)
ON CONFLICT ("semantic_pattern_id") DO NOTHING;
