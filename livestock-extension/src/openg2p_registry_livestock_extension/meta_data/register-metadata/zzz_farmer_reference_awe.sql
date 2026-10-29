-- Approval binding for Farmer-reference change requests (ADD and UPDATE).
--
-- THE SWITCH: the policy_key on the VALUES line below.
--   registry.change_request.livestock-farmer.default
--       every ADD and UPDATE goes to two human stages (the shipped setting)
--   registry.change_request.livestock-farmer.verified-update-skips-review
--       the same, except an UPDATE from the verified Farmer registry skips both
--       stages and is approved by the workflow engine without a task; an ADD is
--       still reviewed by two people
-- Change that one value and seed (or edit the binding in AWE Policy
-- Configuration, which the next seed overwrites). Nothing in code decides this.
--
-- context_field_names asks the platform to copy change_type (ADD or UPDATE) and
-- source ("farmer-registry" only for a verified Farmer change) into the
-- approval request context. It is the same for both policies and harmless to
-- the default one. The reset in zzzzzzzzz_default_binding_reset.sql leaves this
-- binding alone for that reason.
INSERT INTO g2p_registry_awe_policy_configurations
(awe_policy_config_id,policy_scope,register_id,intake_form_id,section_id,policy_type,policy_key,context_field_names)
VALUES ('34eb8fb7-66ed-5c3c-b3a3-cebae5028b64','SECTION','f9c6a359-9563-5a43-b0fe-6c7e452037a3',NULL,'livestock_farmer_identity_section_01',
'registry.change_request','registry.change_request.livestock-farmer.default','["change_type", "source"]')
ON CONFLICT (awe_policy_config_id) DO UPDATE SET
  policy_key=EXCLUDED.policy_key, context_field_names=EXCLUDED.context_field_names;
