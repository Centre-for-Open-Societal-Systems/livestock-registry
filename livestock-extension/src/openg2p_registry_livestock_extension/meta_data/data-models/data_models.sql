-- When a request does not name its data model, the platform tries every row's
-- pattern, so each pattern must be "<jsonpath>=><regex>": a bare "*" makes the
-- matcher raise "Invalid pattern format" and every such ingest fails with
-- SYS-ERR-001. The row is upserted on the mnemonic so databases seeded with
-- the old pattern are repaired by a plain upgrade (ON CONFLICT DO NOTHING
-- never would).
INSERT INTO "public"."data_models" ("data_model_id","data_model_mnemonic","pattern_for_data_model","response_template_document_id","is_active") VALUES
('c331ba96-ac35-4014-9d13-4ef327f6b79b','DCI','$.body.header.data_model=>^DCI$','1f0953d4-f0fb-4336-a126-4d0519a74ffc','TRUE')
ON CONFLICT ("data_model_mnemonic") DO UPDATE SET "pattern_for_data_model" = EXCLUDED."pattern_for_data_model",
  "response_template_document_id" = EXCLUDED."response_template_document_id";

-- DCI response template: dci_commons_response.json.j2
