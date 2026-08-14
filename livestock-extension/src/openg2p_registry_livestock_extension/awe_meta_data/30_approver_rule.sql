-- Demo approvers, one per level. Replace with the real IAM user ids (or
-- switch rule_type to a role rule) when wiring a live deployment.
INSERT INTO "public"."approver_rule" (
    "id",
    "stage_id",
    "rule_type",
    "rule_value",
    "kind",
    "required",
    "created_at",
    "updated_at"
) VALUES
    ('eed867be-436b-5946-868e-147b34bfd7db', '6a963145-a31a-5ee7-a59c-87acf62b1686', 'user', '{"user_id": "kebele.officer"}', 'approver', 'FALSE', NOW(), NOW()),
    ('514cca33-bc53-5a38-9655-5ddd75d6c232', 'cba63287-26e8-5b83-b880-f54bc13e0dda', 'user', '{"user_id": "woreda.officer"}', 'approver', 'FALSE', NOW(), NOW()),
    ('43da187d-629b-51d6-b1fd-1c799e76541a', 'dd7aa8f6-8367-5c0e-bbb9-a9860bc6534c', 'user', '{"user_id": "zone.officer"}', 'approver', 'FALSE', NOW(), NOW()),
    ('16f1d16f-ba1a-5737-92ae-54def73ec500', 'a01b2aba-8768-5a6a-ac61-6278002547d5', 'user', '{"user_id": "region.officer"}', 'approver', 'FALSE', NOW(), NOW()),
    ('3fea9228-4636-5424-a80d-56b8fce8ae1d', '71e2ee0d-0887-5e70-877e-1ca1998ee0e6', 'user', '{"user_id": "kebele.officer"}', 'approver', 'FALSE', NOW(), NOW()),
    ('03f7d4b6-4628-5921-9750-318040c03cd8', '302cbc41-9adc-5ad8-8d51-13cd01961d8c', 'user', '{"user_id": "woreda.officer"}', 'approver', 'FALSE', NOW(), NOW()),
    ('8481aea8-d9d5-5f2d-9360-bd464bb2a820', '37fc6da5-f9e5-5797-b8a1-d15027f75a24', 'user', '{"user_id": "zone.officer"}', 'approver', 'FALSE', NOW(), NOW()),
    ('7cd2036c-4a2b-5981-9c60-894fb50f0415', 'd7636fb3-0fad-5dc3-8043-1f682888c7b3', 'user', '{"user_id": "region.officer"}', 'approver', 'FALSE', NOW(), NOW())
ON CONFLICT ("id") DO NOTHING;
