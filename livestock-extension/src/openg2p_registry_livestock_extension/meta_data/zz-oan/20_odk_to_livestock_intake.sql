-- ODK to Livestock intake: the data model the connector service posts every
-- livestock_registry submission under.
--
--   POST /partner/ingest_data?data_model=ODK_TO_LIVESTOCK_INTAKE
--   {"body": {"header": {"sender_id": "Livestock", "message_id": <instanceID>,
--             "signature": ...}, "message": {"payload": <OData submission>}}}
--
-- The connector names the data model, so the submission is not classified from
-- the payload: it goes straight to the Livestock register's intake form. The
-- semantic pattern below tells the transformation worker where the business
-- payload sits and which enricher prepares it, and the incoming template
-- renders it with odk_to_livestock_intake.j2.
--
-- This replaces two earlier models, which this file retires on every deploy:
--   LIVESTOCK_ODK_MODEL (d2c7a1e4-5f60-4b8a-9c3d-1e2f3a4b5c6d), seeded without a
--   template; and the generic MY_DATA_MODEL with its template IN-TMPL-ODK-1.
-- Their ingested history is moved to the new model. The connector's data model
-- must be ODK_TO_LIVESTOCK_INTAKE before the retired mnemonics stop resolving.
--
-- This folder sorts after data-models/ and registry-inbound-message-rules/, so
-- nothing seeded later re-adds a retired row. Idempotent: every row has a fixed
-- id and is upserted, and the retirement matches explicit ids only.

-- The DCI response template answers the connector. Without it the Partner API
-- cannot serialise its reply, answers 500, and the connector resends the
-- submission on every poll.
INSERT INTO "public"."data_models" ("data_model_id","data_model_mnemonic","pattern_for_data_model","response_template_document_id","is_active") VALUES
('odk_to_livestock_intake','ODK_TO_LIVESTOCK_INTAKE','$.body.header.sender_id=>^Livestock$','1f0953d4-f0fb-4336-a126-4d0519a74ffc','TRUE')
ON CONFLICT ("data_model_id") DO UPDATE SET
    "data_model_mnemonic" = EXCLUDED."data_model_mnemonic",
    "pattern_for_data_model" = EXCLUDED."pattern_for_data_model",
    "response_template_document_id" = EXCLUDED."response_template_document_id",
    "is_active" = EXCLUDED."is_active";

INSERT INTO "public"."incoming_model_key_paths" (
    "key_path_id","data_model_id","key_path_for_message_id","key_path_for_sender",
    "key_path_for_signature","key_path_for_signature_payload","is_list","key_path_for_list_elements"
) VALUES (
    'odk_to_livestock_intake_key_path','odk_to_livestock_intake','$.body.header.message_id','$.body.header.sender_id',
    '$.body.header.signature','$.body[''header'',''message'']','FALSE',''
)
ON CONFLICT ("key_path_id") DO UPDATE SET
    "data_model_id" = EXCLUDED."data_model_id",
    "key_path_for_message_id" = EXCLUDED."key_path_for_message_id",
    "key_path_for_sender" = EXCLUDED."key_path_for_sender",
    "key_path_for_signature" = EXCLUDED."key_path_for_signature",
    "key_path_for_signature_payload" = EXCLUDED."key_path_for_signature_payload",
    "is_list" = EXCLUDED."is_list",
    "key_path_for_list_elements" = EXCLUDED."key_path_for_list_elements";

INSERT INTO "public"."incoming_model_semantic_patterns" (
    "semantic_pattern_id","data_model_id","register_id","intake_form_id",
    "pattern_for_register","pattern_for_intake_form","key_path_for_business_payload","raw_payload_enricher_class"
) VALUES (
    'odk_to_livestock_intake_pattern','odk_to_livestock_intake','997676d3-7008-59f9-b23e-613ad79bbb08','e92e8be1-207f-518e-99c2-8bc21cc1f112',
    '$.body.header.sender_id=>^Livestock$','$.body.header.sender_id=>^Livestock$',
    '$.body.message.payload','G2PDciLivestockCreateEnricherService'
)
ON CONFLICT ("semantic_pattern_id") DO UPDATE SET
    "data_model_id" = EXCLUDED."data_model_id",
    "register_id" = EXCLUDED."register_id",
    "intake_form_id" = EXCLUDED."intake_form_id",
    "pattern_for_register" = EXCLUDED."pattern_for_register",
    "pattern_for_intake_form" = EXCLUDED."pattern_for_intake_form",
    "key_path_for_business_payload" = EXCLUDED."key_path_for_business_payload",
    "raw_payload_enricher_class" = EXCLUDED."raw_payload_enricher_class";

-- The template catalogue row; the image carries the file in the templates
-- bucket under the same name.
INSERT INTO "public"."g2p_registry_documents" ("document_id","document_store_id","bucket","source_filename","created_by","created_at") VALUES
('odk_to_livestock_intake_document','odk_to_livestock_intake.j2','templates','odk_to_livestock_intake.j2','seeder','2026-10-29 00:00:00')
ON CONFLICT ("document_id") DO UPDATE SET
    "document_store_id" = EXCLUDED."document_store_id",
    "bucket" = EXCLUDED."bucket",
    "source_filename" = EXCLUDED."source_filename";

INSERT INTO "public"."incoming_templates" ("template_id","register_id","data_model_id","template_document_id","jsonld_expansion_required","created_at","updated_at") VALUES
('odk_to_livestock_intake_template','997676d3-7008-59f9-b23e-613ad79bbb08','odk_to_livestock_intake','odk_to_livestock_intake_document','FALSE','2026-10-29 00:00:00',NULL)
ON CONFLICT ("template_id") DO UPDATE SET
    "register_id" = EXCLUDED."register_id",
    "data_model_id" = EXCLUDED."data_model_id",
    "template_document_id" = EXCLUDED."template_document_id",
    "jsonld_expansion_required" = EXCLUDED."jsonld_expansion_required";

-- Retire the earlier models. History moves first, so no ingested submission is
-- left pointing at a model that no longer exists.
UPDATE "public"."incoming_raw_data"
   SET "data_model_id" = 'odk_to_livestock_intake'
 WHERE "data_model_id" IN ('d2c7a1e4-5f60-4b8a-9c3d-1e2f3a4b5c6d','MY_DATA_MODEL');

UPDATE "public"."incoming_classified_data"
   SET "data_model_id" = 'odk_to_livestock_intake',
       "semantic_pattern_id" = CASE
           WHEN "semantic_pattern_id" IN ('9e8d7c6b-5a4f-4e3d-9c2b-1a0f9e8d7c6b','SP-ODK-LIVESTOCK-1')
           THEN 'odk_to_livestock_intake_pattern' ELSE "semantic_pattern_id" END
 WHERE "data_model_id" IN ('d2c7a1e4-5f60-4b8a-9c3d-1e2f3a4b5c6d','MY_DATA_MODEL')
    OR "semantic_pattern_id" IN ('9e8d7c6b-5a4f-4e3d-9c2b-1a0f9e8d7c6b','SP-ODK-LIVESTOCK-1');

-- Then the configuration, children first, by explicit id or explicit model.
DELETE FROM "public"."incoming_templates" WHERE "template_id" = 'IN-TMPL-ODK-1';

DELETE FROM "public"."g2p_registry_documents"
 WHERE ("document_id" = '8d92ac11-b93b-4a13-9f06-3f4ed20399cc'
        OR ("bucket" = 'templates' AND "document_store_id" = 'ls_odk_transform.j2'))
   AND NOT EXISTS (SELECT 1 FROM "public"."incoming_templates" t
                    WHERE t."template_document_id" = "g2p_registry_documents"."document_id");

DELETE FROM "public"."incoming_model_semantic_patterns"
 WHERE "semantic_pattern_id" IN ('SP-ODK-LIVESTOCK-1','9e8d7c6b-5a4f-4e3d-9c2b-1a0f9e8d7c6b');

DELETE FROM "public"."incoming_model_key_paths"
 WHERE "key_path_id" IN ('my_key_path','7b8c9d0e-1f2a-4b3c-8d4e-5f6a7b8c9d0e')
    OR "data_model_id" IN ('MY_DATA_MODEL','d2c7a1e4-5f60-4b8a-9c3d-1e2f3a4b5c6d');

DELETE FROM "public"."data_models"
 WHERE "data_model_id" IN ('MY_DATA_MODEL','d2c7a1e4-5f60-4b8a-9c3d-1e2f3a4b5c6d');

-- Guard: fail the seed if any trace of a retired model survives.
DO $$
DECLARE
    leftovers integer;
BEGIN
    SELECT (SELECT count(*) FROM "public"."data_models"
             WHERE "data_model_mnemonic" IN ('LIVESTOCK_ODK_MODEL','MY_DATA_MODEL')
                OR "data_model_id" IN ('d2c7a1e4-5f60-4b8a-9c3d-1e2f3a4b5c6d','MY_DATA_MODEL'))
         + (SELECT count(*) FROM "public"."incoming_raw_data"
             WHERE "data_model_id" IN ('d2c7a1e4-5f60-4b8a-9c3d-1e2f3a4b5c6d','MY_DATA_MODEL','LIVESTOCK_ODK_MODEL'))
         + (SELECT count(*) FROM "public"."incoming_classified_data"
             WHERE "data_model_id" IN ('d2c7a1e4-5f60-4b8a-9c3d-1e2f3a4b5c6d','MY_DATA_MODEL','LIVESTOCK_ODK_MODEL'))
      INTO leftovers;
    IF leftovers <> 0 THEN
        RAISE EXCEPTION 'Retired livestock ODK data model (LIVESTOCK_ODK_MODEL / MY_DATA_MODEL) still referenced by % rows', leftovers;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM "public"."data_models"
                    WHERE "data_model_id" = 'odk_to_livestock_intake'
                      AND "data_model_mnemonic" = 'ODK_TO_LIVESTOCK_INTAKE') THEN
        RAISE EXCEPTION 'Data model ODK_TO_LIVESTOCK_INTAKE is missing';
    END IF;
END
$$;
