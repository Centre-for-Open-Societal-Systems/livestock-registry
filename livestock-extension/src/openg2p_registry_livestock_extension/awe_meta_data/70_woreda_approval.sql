-- Livestock approval: the field officer submits, and one approval by a staff
-- member holding the Woreda Approver role of the livestock portal completes the
-- request. Every holder of the role gets a task and one decision is enough;
-- admin stays on the stage so a role with no holders does not reject the request.
--
-- The role is read from Keycloak when the stage starts, so giving an officer the
-- role is enough to add an approver. The record's place is not considered.
-- The bindings in meta_data/register-metadata name these policies. An active
-- policy version is immutable, so a different rule needs a new version or key.
INSERT INTO public.approval_policy (id,policy_key,version,name,description,status,artifact_type,created_by,forbid_self_approval,forbid_repeat_approvers,created_at,updated_at) VALUES
('c88fae8a-8e70-58e8-be80-e044f9f7ca7e','registry.change_request.livestock.woreda',1,'Livestock change request - Woreda approval','One approval by a Woreda Approver','active','registry.change_request','seed',FALSE,FALSE,NOW(),NOW()),
('21542b8a-d350-5540-9ecb-11e9fd2911ca','registry.intake_form.livestock.woreda',1,'Livestock intake - Woreda approval','One approval by a Woreda Approver','active','registry.intake_form','seed',FALSE,FALSE,NOW(),NOW())
ON CONFLICT (policy_key,version) DO NOTHING;

INSERT INTO public.approval_stage (id,policy_id,stage_order,name,mode,mode_value,sla_hours,parallel_group,skip_if,on_empty,on_breach,escalation_rules_json,created_at,updated_at)
SELECT v.id,p.id,v.stage_order,v.name,'any-n',1,CAST(NULL AS integer),CAST(NULL AS integer),'null','block',CAST(NULL AS integer),'null',NOW(),NOW()
FROM (VALUES
('3b3f4e50-9e80-5e3f-a065-c7be9cd47910','registry.change_request.livestock.woreda',1,'Woreda approval'),
('0a08f83b-e31d-5096-b405-fefdb8443f87','registry.intake_form.livestock.woreda',1,'Woreda approval')) AS v(id,policy_key,stage_order,name)
JOIN public.approval_policy p ON p.policy_key=v.policy_key AND p.version=1
WHERE NOT EXISTS (SELECT 1 FROM public.approval_stage s WHERE s.policy_id=p.id AND s.stage_order=v.stage_order)
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.approver_rule (id,stage_id,rule_type,rule_value,kind,required,created_at,updated_at)
SELECT v.id,s.id,v.rule_type,v.rule_value::json,'approver',FALSE,NOW(),NOW()
FROM (VALUES
('c101abb9-b801-5743-a577-710817e21cdd','registry.change_request.livestock.woreda',1,'role','{"role": "Woreda Approver", "client": "livestock-registry-staff-portal"}'),
('b55ab026-3f25-5ada-b2a7-9706d7bb313f','registry.change_request.livestock.woreda',1,'user','{"user_id": "admin"}'),
('2a7b5d33-1bad-53d0-854d-33cd44c50704','registry.intake_form.livestock.woreda',1,'role','{"role": "Woreda Approver", "client": "livestock-registry-staff-portal"}'),
('d3ffb8d1-3dc8-56ff-832c-282e6df03944','registry.intake_form.livestock.woreda',1,'user','{"user_id": "admin"}')) AS v(id,policy_key,stage_order,rule_type,rule_value)
JOIN public.approval_policy p ON p.policy_key=v.policy_key AND p.version=1
JOIN public.approval_stage s ON s.policy_id=p.id AND s.stage_order=v.stage_order
WHERE NOT EXISTS (SELECT 1 FROM public.approver_rule r WHERE r.stage_id=s.id AND r.rule_type=v.rule_type AND r.rule_value::text=v.rule_value)
ON CONFLICT (id) DO NOTHING;
