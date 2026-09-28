INSERT INTO "public"."approval_policy" (
    "id",
    "policy_key",
    "version",
    "name",
    "description",
    "status",
    "artifact_type",
    "created_by",
    "forbid_self_approval",
    "forbid_repeat_approvers",
    "created_at",
    "updated_at"
) VALUES
    ('b2477cdc-7db9-5f2a-bda9-828a713c5b4d', 'registry.change_request.livestock', 1, 'Policy for Livestock Change Request', NULL, 'active', 'registry.change_request', 'seed', 'FALSE', 'FALSE', NOW(), NOW()),
    ('907339cb-744e-5fe9-9805-df7416d81dbe', 'registry.intake_form.livestock', 1, 'Policy for Livestock Intake Form', NULL, 'active', 'registry.intake_form', 'seed', 'FALSE', 'FALSE', NOW(), NOW())
ON CONFLICT ("id") DO NOTHING;
