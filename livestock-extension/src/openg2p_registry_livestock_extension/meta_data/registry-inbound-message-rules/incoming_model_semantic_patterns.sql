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
);
