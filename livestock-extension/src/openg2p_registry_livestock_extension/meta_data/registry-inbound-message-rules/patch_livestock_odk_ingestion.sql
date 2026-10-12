-- Patch for environments seeded before the Livestock ODK data model existed
-- (dev / staging registry DB). Same rows as data_models.sql,
-- incoming_model_key_paths.sql and incoming_model_semantic_patterns.sql; safe
-- to re-run. Runs against the registry (livestock) database.

INSERT INTO "public"."data_models" ("data_model_id","data_model_mnemonic","pattern_for_data_model","response_template_document_id","is_active") VALUES
-- No response template: the ODK connector reads the platform's own reply
-- (response_body.response_payload.correlation_id). The DCI response template
-- reshaped it into {"message": {"ack_status", "correlation_id"}}, which the
-- connector does not read, so every run was logged without its correlation id.
('d2c7a1e4-5f60-4b8a-9c3d-1e2f3a4b5c6d','LIVESTOCK_ODK_MODEL','$.body.header.sender_id=>^Livestock$',NULL,'TRUE')
ON CONFLICT ("data_model_id") DO UPDATE SET "response_template_document_id" = NULL;

INSERT INTO "public"."incoming_model_key_paths" (
    "key_path_id","data_model_id","key_path_for_message_id","key_path_for_sender",
    "key_path_for_signature","key_path_for_signature_payload","is_list","key_path_for_list_elements"
) VALUES (
    '7b8c9d0e-1f2a-4b3c-8d4e-5f6a7b8c9d0e','d2c7a1e4-5f60-4b8a-9c3d-1e2f3a4b5c6d','$.body.header.message_id','$.body.header.sender_id',
    '$.body.header.signature','$.body[''header'',''message'']','FALSE',''
)
ON CONFLICT ("key_path_id") DO NOTHING;

INSERT INTO "public"."incoming_model_semantic_patterns" (
    "semantic_pattern_id","data_model_id","register_id","intake_form_id",
    "pattern_for_register","pattern_for_intake_form","key_path_for_business_payload","raw_payload_enricher_class"
) VALUES (
    '9e8d7c6b-5a4f-4e3d-9c2b-1a0f9e8d7c6b','d2c7a1e4-5f60-4b8a-9c3d-1e2f3a4b5c6d','997676d3-7008-59f9-b23e-613ad79bbb08','e92e8be1-207f-518e-99c2-8bc21cc1f112',
    '$.body.header.sender_id=>^Livestock$','$.body.header.sender_id=>^Livestock$',
    '$.body.message.payload','G2PDciLivestockCreateEnricherService'
)
ON CONFLICT ("semantic_pattern_id") DO NOTHING;
