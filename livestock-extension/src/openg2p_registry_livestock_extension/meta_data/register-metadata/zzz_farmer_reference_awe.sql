-- Fresh-install binding only; no existing bindings or IAM assignments are removed.
-- The shared AWE policy is provisioned through its standard administration API
-- from docs/refactor/configuration/farmer-reference-awe-policy.json.
INSERT INTO g2p_registry_awe_policy_configurations
(awe_policy_config_id,policy_scope,register_id,intake_form_id,section_id,policy_type,policy_key,context_field_names)
VALUES ('34eb8fb7-66ed-5c3c-b3a3-cebae5028b64','SECTION','f9c6a359-9563-5a43-b0fe-6c7e452037a3',NULL,'livestock_farmer_identity_section_01',
'registry.change_request','coss.livestock.farmer-reference.v1','["farmer_reference_woreda_id","farmer_reference_approver_ids"]')
ON CONFLICT (awe_policy_config_id) DO NOTHING;
