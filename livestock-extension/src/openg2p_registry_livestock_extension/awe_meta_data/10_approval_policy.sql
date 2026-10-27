-- OpenG2P Farmer 1.2 default approval pattern. Domain-specific keys keep
-- old policies and in-flight tasks intact; no role/grant/task mutation.
INSERT INTO public.approval_policy (id,policy_key,version,name,description,status,artifact_type,created_by,forbid_self_approval,forbid_repeat_approvers,created_at,updated_at) VALUES
('b9d6e710-aead-5d13-9aec-cc4a86e6a9d5','registry.change_request.livestock.default',1,'Livestock change request - OpenG2P defaults',NULL,'active','registry.change_request','seed',FALSE,FALSE,NOW(),NOW()),
('b9fb57e1-0a17-5354-a6ab-042a574f6ea8','registry.change_request.livestock-farmer.default',1,'Farmer reference change request - OpenG2P defaults',NULL,'active','registry.change_request','seed',FALSE,FALSE,NOW(),NOW()),
('131bcb0f-6459-51d7-a525-0e9f12160db7','registry.intake_form.livestock.default',1,'Livestock intake - OpenG2P defaults',NULL,'active','registry.intake_form','seed',FALSE,FALSE,NOW(),NOW())
ON CONFLICT (policy_key,version) DO NOTHING;
