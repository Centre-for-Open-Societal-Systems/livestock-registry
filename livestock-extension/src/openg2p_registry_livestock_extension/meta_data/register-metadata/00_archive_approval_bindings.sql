-- Preserve complete original configuration before any seed upserts.
INSERT INTO "public".coss_approval_binding_archive (binding_id,content_hash,original_binding,reason,archived_at)
SELECT c.awe_policy_config_id,md5(to_jsonb(c)::text),to_jsonb(c),'OpenG2P default approval reset',CURRENT_TIMESTAMP
FROM "public".g2p_registry_awe_policy_configurations c
WHERE c.register_id IN ('997676d3-7008-59f9-b23e-613ad79bbb08','f9c6a359-9563-5a43-b0fe-6c7e452037a3') AND c.policy_type IN ('registry.change_request','change_request','registry.intake_form','intake_form') AND (c.policy_key NOT LIKE '%.default' OR c.context_field_names IS NOT NULL)
ON CONFLICT (binding_id,content_hash) DO NOTHING;
