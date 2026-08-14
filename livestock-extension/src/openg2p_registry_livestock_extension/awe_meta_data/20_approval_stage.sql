-- Kebele -> Woreda -> Zone -> Region, the ladder enforced in
-- g2p_livestock_registry/models/livestock_registry.py.
INSERT INTO "public"."approval_stage" (
    "id",
    "policy_id",
    "stage_order",
    "name",
    "mode",
    "mode_value",
    "sla_hours",
    "parallel_group",
    "skip_if",
    "on_empty",
    "on_breach",
    "escalation_rules_json",
    "created_at",
    "updated_at"
) VALUES
    ('6a963145-a31a-5ee7-a59c-87acf62b1686', 'b2477cdc-7db9-5f2a-bda9-828a713c5b4d', 1, 'Stage 1 Kebele Approver', 'all', NULL, NULL, NULL, 'null', 'block', NULL, 'null', NOW(), NOW()),
    ('cba63287-26e8-5b83-b880-f54bc13e0dda', 'b2477cdc-7db9-5f2a-bda9-828a713c5b4d', 2, 'Stage 2 Woreda Approver', 'all', NULL, NULL, NULL, 'null', 'block', NULL, 'null', NOW(), NOW()),
    ('dd7aa8f6-8367-5c0e-bbb9-a9860bc6534c', 'b2477cdc-7db9-5f2a-bda9-828a713c5b4d', 3, 'Stage 3 Zone Approver', 'all', NULL, NULL, NULL, 'null', 'block', NULL, 'null', NOW(), NOW()),
    ('a01b2aba-8768-5a6a-ac61-6278002547d5', 'b2477cdc-7db9-5f2a-bda9-828a713c5b4d', 4, 'Stage 4 Region Approver', 'all', NULL, NULL, NULL, 'null', 'block', NULL, 'null', NOW(), NOW()),
    ('71e2ee0d-0887-5e70-877e-1ca1998ee0e6', '907339cb-744e-5fe9-9805-df7416d81dbe', 1, 'Stage 1 Kebele Approver', 'all', NULL, NULL, NULL, 'null', 'block', NULL, 'null', NOW(), NOW()),
    ('302cbc41-9adc-5ad8-8d51-13cd01961d8c', '907339cb-744e-5fe9-9805-df7416d81dbe', 2, 'Stage 2 Woreda Approver', 'all', NULL, NULL, NULL, 'null', 'block', NULL, 'null', NOW(), NOW()),
    ('37fc6da5-f9e5-5797-b8a1-d15027f75a24', '907339cb-744e-5fe9-9805-df7416d81dbe', 3, 'Stage 3 Zone Approver', 'all', NULL, NULL, NULL, 'null', 'block', NULL, 'null', NOW(), NOW()),
    ('d7636fb3-0fad-5dc3-8043-1f682888c7b3', '907339cb-744e-5fe9-9805-df7416d81dbe', 4, 'Stage 4 Region Approver', 'all', NULL, NULL, NULL, 'null', 'block', NULL, 'null', NOW(), NOW())
ON CONFLICT ("id") DO NOTHING;
