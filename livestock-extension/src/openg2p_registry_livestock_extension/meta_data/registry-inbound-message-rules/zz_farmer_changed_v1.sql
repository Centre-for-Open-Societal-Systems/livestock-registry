-- FARMER_CHANGED_V1: the Farmer registry's change notice under its readable name
-- (topic and event type farmer-registry.farmer.changed.v1). It sits next to
-- FARMER_REFERENCE_CHANGED_V1 (zz_farmer_reference.sql) until every sender has
-- moved over; it accepts the old event type as well, so the new connectors work
-- before and after the Farmer registry switches its topic. The old rows are then
-- removed by explicit id. Same key path, routing and transform as the old
-- model; templates carry this registry's prefix so they never collide in the
-- shared templates bucket.
INSERT INTO public.g2p_registry_documents ("document_id","document_store_id","bucket","source_filename","created_by","created_at") VALUES
('livestock_farmer_changed_v1_update_document','livestock_farmer_changed_v1_update.j2','templates','livestock_farmer_changed_v1_update.j2','seeder','2026-10-29 00:00:00'),
('livestock_farmer_changed_v1_response_document','livestock_farmer_changed_v1_response.j2','templates','livestock_farmer_changed_v1_response.j2','seeder','2026-10-29 00:00:00')
ON CONFLICT ("document_id") DO UPDATE SET "document_store_id" = EXCLUDED."document_store_id", "source_filename" = EXCLUDED."source_filename";

INSERT INTO public.data_models ("data_model_id","data_model_mnemonic","pattern_for_data_model","response_template_document_id","is_active") VALUES
('farmer_changed_v1','FARMER_CHANGED_V1','$.body.message.payload.event_type=>^(farmer-registry[.]farmer[.]changed[.]v1|farmer_reference[.]changed[.]v1)$','livestock_farmer_changed_v1_response_document',TRUE)
ON CONFLICT ("data_model_id") DO UPDATE SET "data_model_mnemonic" = EXCLUDED."data_model_mnemonic", "pattern_for_data_model" = EXCLUDED."pattern_for_data_model", "response_template_document_id" = EXCLUDED."response_template_document_id", "is_active" = EXCLUDED."is_active";

INSERT INTO public.incoming_model_key_paths ("key_path_id","data_model_id","key_path_for_message_id","key_path_for_sender","key_path_for_signature","key_path_for_signature_payload","is_list","key_path_for_list_elements") VALUES
('farmer_changed_v1_key_path','farmer_changed_v1','$.body.header.message_id','$.body.header.sender_id','$.body.header.signature','$.body.message.payload',FALSE,'')
ON CONFLICT ("key_path_id") DO NOTHING;

INSERT INTO public.incoming_model_register_semantic_patterns ("register_semantic_pattern_id","data_model_id","register_id","pattern_for_register","key_path_for_record_identifier") VALUES
('farmer_changed_v1_register_pattern','farmer_changed_v1','f9c6a359-9563-5a43-b0fe-6c7e452037a3','$.body.message.payload.event_type=>^(farmer-registry[.]farmer[.]changed[.]v1|farmer_reference[.]changed[.]v1)$','$.body.message.payload.farmer_id')
ON CONFLICT ("register_semantic_pattern_id") DO UPDATE SET "pattern_for_register" = EXCLUDED."pattern_for_register";

INSERT INTO public.incoming_model_semantic_patterns ("semantic_pattern_id","data_model_id","register_id","intake_form_id","section_id","pattern_for_register","pattern_for_intake_form","pattern_for_section","key_path_for_business_payload","raw_payload_enricher_class") VALUES
('farmer_changed_v1_pattern','farmer_changed_v1','f9c6a359-9563-5a43-b0fe-6c7e452037a3',NULL,'livestock_farmer_identity_section_01','$.body.message.payload.event_type=>^(farmer-registry[.]farmer[.]changed[.]v1|farmer_reference[.]changed[.]v1)$','$.body.message.payload.event_type=>^NEVER_ADD$','$.body.message.payload.event_type=>^(farmer-registry[.]farmer[.]changed[.]v1|farmer_reference[.]changed[.]v1)$','$.body.message.payload','FarmerChangedEnricher')
ON CONFLICT ("semantic_pattern_id") DO UPDATE SET "pattern_for_register" = EXCLUDED."pattern_for_register", "pattern_for_section" = EXCLUDED."pattern_for_section", "raw_payload_enricher_class" = EXCLUDED."raw_payload_enricher_class";

INSERT INTO public.incoming_templates ("template_id","register_id","data_model_id","template_document_id","jsonld_expansion_required","created_at") VALUES
('farmer_changed_v1_template','f9c6a359-9563-5a43-b0fe-6c7e452037a3','farmer_changed_v1','livestock_farmer_changed_v1_update_document',FALSE,'2026-10-29 00:00:00')
ON CONFLICT ("template_id") DO NOTHING;
