-- OpenG2P Farmer 1.2 default approval pattern. Domain-specific keys keep
-- old policies and in-flight tasks intact; no role/grant/task mutation.
-- Each stage is satisfied by one decision (any-n, 1): the named officer or admin.
INSERT INTO public.approval_stage (id,policy_id,stage_order,name,mode,mode_value,sla_hours,parallel_group,skip_if,on_empty,on_breach,escalation_rules_json,created_at,updated_at)
SELECT v.id,p.id,v.stage_order,v.name,'any-n',1,CAST(NULL AS integer),CAST(NULL AS integer),'null','block',CAST(NULL AS integer),'null',NOW(),NOW()
FROM (VALUES
('a5ca8625-143d-57b3-b220-912bdeda193d','registry.change_request.livestock.default',1,'First approval'),
('e072783f-27ad-582b-b30f-a942d329850a','registry.change_request.livestock.default',2,'Second approval'),
('586da3d5-65f1-566a-80ea-3b4b30d17b82','registry.change_request.livestock-farmer.default',1,'First approval'),
('8536ea7d-7c57-5cb6-af1c-54f992ea3059','registry.change_request.livestock-farmer.default',2,'Second approval'),
('580c4a2b-c638-5099-aac5-72860e9ff4ff','registry.intake_form.livestock.default',1,'First approval'),
('23cd6619-b044-55a9-aa1c-ee3b190950d5','registry.intake_form.livestock.default',2,'Second approval')) AS v(id,policy_key,stage_order,name)
JOIN public.approval_policy p ON p.policy_key=v.policy_key AND p.version=1
WHERE NOT EXISTS (SELECT 1 FROM public.approval_stage s WHERE s.policy_id=p.id AND s.stage_order=v.stage_order)
ON CONFLICT (id) DO NOTHING;
