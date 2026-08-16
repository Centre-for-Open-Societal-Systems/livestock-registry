-- Which registry artefacts route through AWE.
--
-- REGISTER      — an update change request on a Livestock record opens an
--                 approval request and is applied only once approved.
-- INTAKE_FORM   — finalizing an intake submission opens an approval request
--                 too. This is what puts the submission into the staff
--                 portal's "My Tasks" tile: that count comes from
--                 /awe/my_task_stats, so a submission with no AWE task is
--                 invisible there no matter how many are pending approval.
--
-- Both point at the single-stage policies seeded in awe_meta_data/, whose
-- approver is the Registry Admin.
INSERT INTO "public"."g2p_registry_awe_policy_configurations" (
    "awe_policy_config_id",
    "policy_scope",
    "register_id",
    "intake_form_id",
    "section_id",
    "policy_type",
    "policy_key",
    "context_field_names"
) VALUES
    ('7c1f8a92-4b3d-4e15-9a26-5d8e0f3b71a4', 'REGISTER', '997676d3-7008-59f9-b23e-613ad79bbb08', '', '', 'registry.change_request', 'registry.change_request.livestock', 'null'),
    ('8d2e9ba3-5c4e-4f26-ab37-6e9f1a4c82b5', 'INTAKE_FORM', '997676d3-7008-59f9-b23e-613ad79bbb08', 'e92e8be1-207f-518e-99c2-8bc21cc1f112', '', 'registry.intake_form', 'registry.intake_form.livestock', 'null')
ON CONFLICT ("awe_policy_config_id") DO NOTHING;
