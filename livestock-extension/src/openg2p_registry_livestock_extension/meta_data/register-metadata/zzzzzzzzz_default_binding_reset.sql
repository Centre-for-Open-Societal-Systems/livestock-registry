-- Native policy resolution requires exactly one binding per effective scope.
-- Preserve full snapshots/IDs before retiring duplicate metadata only. AWE
-- policies, requests, tasks, decisions, IAM grants and domain rows are untouched.
-- The Farmer-reference section binding is owned by zzz_farmer_reference_awe.sql
-- (policy switch and context fields) and is excluded from the reset.
INSERT INTO "public".coss_approval_binding_archive (binding_id,content_hash,original_binding,reason,archived_at)
SELECT c.awe_policy_config_id,md5(to_jsonb(c)::text),to_jsonb(c),'OpenG2P default approval reset',CURRENT_TIMESTAMP
FROM "public".g2p_registry_awe_policy_configurations c
WHERE c.register_id IN ('997676d3-7008-59f9-b23e-613ad79bbb08','f9c6a359-9563-5a43-b0fe-6c7e452037a3') AND c.policy_type IN ('registry.change_request','change_request','registry.intake_form','intake_form') AND c.awe_policy_config_id <> '34eb8fb7-66ed-5c3c-b3a3-cebae5028b64' AND (c.policy_key NOT LIKE '%.default' OR c.context_field_names IS NOT NULL)
ON CONFLICT (binding_id,content_hash) DO NOTHING;

UPDATE "public".g2p_registry_awe_policy_configurations c
SET policy_key=m.policy_key,context_field_names=NULL
FROM (VALUES
('997676d3-7008-59f9-b23e-613ad79bbb08','change_request','registry.change_request.livestock.default'),
('f9c6a359-9563-5a43-b0fe-6c7e452037a3','change_request','registry.change_request.livestock-farmer.default'),
('997676d3-7008-59f9-b23e-613ad79bbb08','intake_form','registry.intake_form.livestock.default')) m(register_id,artifact,policy_key)
WHERE c.awe_policy_config_id <> '34eb8fb7-66ed-5c3c-b3a3-cebae5028b64' AND c.register_id=m.register_id AND regexp_replace(c.policy_type,'^registry[.]','')=m.artifact
  AND (c.policy_key IS DISTINCT FROM m.policy_key OR c.context_field_names IS NOT NULL);

WITH ranked AS (SELECT c.awe_policy_config_id,row_number() OVER (PARTITION BY c.register_id,regexp_replace(c.policy_type,'^registry[.]',''),c.policy_scope,CASE WHEN c.policy_scope='SECTION' THEN coalesce(c.section_id,'') WHEN c.policy_scope='INTAKE_FORM' THEN coalesce(c.intake_form_id,'') ELSE '' END ORDER BY CASE WHEN c.awe_policy_config_id IN ('c3fd39f4-7dbc-5358-8d84-edd8ba780125','18eedc19-cb83-50d1-bc34-c1b03ee51815','506574e4-701d-5e8e-84db-545698ef007a','34eb8fb7-66ed-5c3c-b3a3-cebae5028b64') THEN 0 ELSE 1 END,c.awe_policy_config_id) AS position FROM "public".g2p_registry_awe_policy_configurations c WHERE c.register_id IN ('997676d3-7008-59f9-b23e-613ad79bbb08','f9c6a359-9563-5a43-b0fe-6c7e452037a3') AND c.policy_type IN ('registry.change_request','change_request','registry.intake_form','intake_form'))
INSERT INTO "public".coss_approval_binding_archive (binding_id,content_hash,original_binding,reason,archived_at)
SELECT c.awe_policy_config_id,md5(to_jsonb(c)::text),to_jsonb(c),'Duplicate native approval binding',CURRENT_TIMESTAMP
FROM "public".g2p_registry_awe_policy_configurations c JOIN ranked r ON r.awe_policy_config_id=c.awe_policy_config_id
WHERE r.position>1 ON CONFLICT (binding_id,content_hash) DO NOTHING;

WITH ranked AS (SELECT c.awe_policy_config_id,row_number() OVER (PARTITION BY c.register_id,regexp_replace(c.policy_type,'^registry[.]',''),c.policy_scope,CASE WHEN c.policy_scope='SECTION' THEN coalesce(c.section_id,'') WHEN c.policy_scope='INTAKE_FORM' THEN coalesce(c.intake_form_id,'') ELSE '' END ORDER BY CASE WHEN c.awe_policy_config_id IN ('c3fd39f4-7dbc-5358-8d84-edd8ba780125','18eedc19-cb83-50d1-bc34-c1b03ee51815','506574e4-701d-5e8e-84db-545698ef007a','34eb8fb7-66ed-5c3c-b3a3-cebae5028b64') THEN 0 ELSE 1 END,c.awe_policy_config_id) AS position FROM "public".g2p_registry_awe_policy_configurations c WHERE c.register_id IN ('997676d3-7008-59f9-b23e-613ad79bbb08','f9c6a359-9563-5a43-b0fe-6c7e452037a3') AND c.policy_type IN ('registry.change_request','change_request','registry.intake_form','intake_form'))
DELETE FROM "public".g2p_registry_awe_policy_configurations c USING ranked r
WHERE c.awe_policy_config_id=r.awe_policy_config_id AND r.position>1
  AND EXISTS (SELECT 1 FROM "public".coss_approval_binding_archive a
    WHERE a.binding_id=c.awe_policy_config_id AND a.content_hash=md5(to_jsonb(c)::text));
