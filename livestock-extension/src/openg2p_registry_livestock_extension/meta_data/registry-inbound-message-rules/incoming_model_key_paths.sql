INSERT INTO "public"."incoming_model_key_paths" (
    "key_path_id",
    "data_model_id",
    "key_path_for_message_id",
    "key_path_for_sender",
    "key_path_for_signature",
    "key_path_for_signature_payload",
    "is_list",
    "key_path_for_list_elements"
) VALUES (
    '4a5d9a8e-ffef-466a-9d00-d8bd39b0337c',
    'c331ba96-ac35-4014-9d13-4ef327f6b79b',
    '$.body.header.message_id',
    '$.body.header.sender_id',
    '$.body.signature',
    '$.body[''header'',''message'']',
    'FALSE',
    ''
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
INSERT INTO "public"."incoming_model_key_paths" (
    "key_path_id","data_model_id","key_path_for_message_id","key_path_for_sender",
    "key_path_for_signature","key_path_for_signature_payload","is_list","key_path_for_list_elements"
) VALUES (
    '7b8c9d0e-1f2a-4b3c-8d4e-5f6a7b8c9d0e','d2c7a1e4-5f60-4b8a-9c3d-1e2f3a4b5c6d','$.body.header.message_id','$.body.header.sender_id',
    '$.body.header.signature','$.body[''header'',''message'']','FALSE',''
)
ON CONFLICT ("key_path_id") DO NOTHING;
