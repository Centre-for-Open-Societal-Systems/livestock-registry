-- Optional policy for Farmer-reference change requests: the default two human
-- stages, except that an UPDATE which came from the verified Farmer registry is
-- approved without review. Each stage carries the same skip_if rule (JSONLogic
-- over the request context); when every stage is skipped the workflow engine
-- approves the request itself ("all_stages_skipped") and sends the usual
-- request_approved callback. An ADD, or anything unverified, is never skipped.
--
-- Seeding this policy changes nothing: no binding points at it. It takes effect
-- only when the Farmer-reference binding in
-- meta_data/register-metadata/zzz_farmer_reference_awe.sql names it. An active
-- policy version is immutable, so a different rule needs a new version or key.
INSERT INTO public.approval_policy (id,policy_key,version,name,description,status,artifact_type,created_by,forbid_self_approval,forbid_repeat_approvers,created_at,updated_at) VALUES
('11c0cf8e-b566-5686-8e2b-c16c33f034d5','registry.change_request.livestock-farmer.verified-update-skips-review',1,'Farmer reference change request - verified updates skip review','Default two human stages; an UPDATE from the verified Farmer registry skips both','active','registry.change_request','seed',FALSE,FALSE,NOW(),NOW())
ON CONFLICT (policy_key,version) DO NOTHING;

INSERT INTO public.approval_stage (id,policy_id,stage_order,name,mode,mode_value,sla_hours,parallel_group,skip_if,on_empty,on_breach,escalation_rules_json,created_at,updated_at)
SELECT v.id,p.id,v.stage_order,v.name,'any-n',1,CAST(NULL AS integer),CAST(NULL AS integer),CAST('{"and": [{"==": [{"var": "change_type"}, "UPDATE"]}, {"==": [{"var": "source"}, "farmer-registry"]}]}' AS json),'block',CAST(NULL AS integer),'null',NOW(),NOW()
FROM (VALUES
('d2d6c2ea-3e4d-51e5-8e97-78a273e26ecc','registry.change_request.livestock-farmer.verified-update-skips-review',1,'Stage 1 Officers'),
('96243f6c-b4d1-5bca-8f08-aaefad9d04ca','registry.change_request.livestock-farmer.verified-update-skips-review',2,'Stage 2 Officers')) AS v(id,policy_key,stage_order,name)
JOIN public.approval_policy p ON p.policy_key=v.policy_key AND p.version=1
WHERE NOT EXISTS (SELECT 1 FROM public.approval_stage s WHERE s.policy_id=p.id AND s.stage_order=v.stage_order)
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.approver_rule (id,stage_id,rule_type,rule_value,kind,required,created_at,updated_at)
SELECT v.id,s.id,'user',v.rule_value::json,'approver',FALSE,NOW(),NOW()
FROM (VALUES
('0975d9ac-a2ce-5cb6-81a3-ff7e0997cf36','registry.change_request.livestock-farmer.verified-update-skips-review',1,'{"user_id": "alex.carter"}'),
('7a5d8418-0e79-598c-affa-08f426b3523d','registry.change_request.livestock-farmer.verified-update-skips-review',1,'{"user_id": "admin"}'),
('5da1648f-5ba4-5eae-9487-0aabd67c7b66','registry.change_request.livestock-farmer.verified-update-skips-review',2,'{"user_id": "nina.patel"}'),
('e6925d06-49e1-5e8d-926d-798a0e25a657','registry.change_request.livestock-farmer.verified-update-skips-review',2,'{"user_id": "admin"}')) AS v(id,policy_key,stage_order,rule_value)
JOIN public.approval_policy p ON p.policy_key=v.policy_key AND p.version=1
JOIN public.approval_stage s ON s.policy_id=p.id AND s.stage_order=v.stage_order
WHERE NOT EXISTS (SELECT 1 FROM public.approver_rule r WHERE r.stage_id=s.id AND r.rule_type='user' AND r.rule_value::text=v.rule_value)
ON CONFLICT (id) DO NOTHING;
