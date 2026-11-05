"""Two native stages per policy, each completed by the named officer or admin; never auto-approval."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN_RULE = {"rule_type": "user", "rule_value": {"user_id": "admin"}, "kind": "approver", "required": False}


def test_all_domain_and_reference_policies_complete_on_the_named_officer_or_admin():
    policies = json.loads((ROOT / "docs/refactor/configuration/default-awe-policies.json").read_text())
    assert len(policies) == 3
    assert len({p["policy_key"] for p in policies}) == 3
    for policy in policies:
        assert policy["policy_key"].endswith(".default")
        assert policy["forbid_self_approval"] is False
        assert policy["forbid_repeat_approvers"] is False
        assert [stage["stage_order"] for stage in policy["stages"]] == [1, 2]
        for stage, reviewer in zip(policy["stages"], ("alex.carter", "nina.patel")):
            assert stage["mode"] == "any-n" and stage["mode_value"] == 1
            assert stage["on_empty"] == "block"
            assert stage["rules"] == [{"rule_type": "user", "rule_value": {"user_id": reviewer},
                                       "kind": "approver", "required": False}, ADMIN_RULE]


def test_seeds_match_the_declared_policies_and_move_older_databases_in_place():
    package = next(ROOT.glob("*-extension/src/openg2p_registry_*_extension"))
    seeds = package / "awe_meta_data"
    assert sorted(p.name for p in seeds.iterdir() if p.is_file()) == [
        "10_approval_policy.sql", "20_approval_stage.sql", "30_approver_rule.sql",
        "40_callback_secret.sql.tpl", "50_either_officer_or_admin.sql", "60_verified_update_skips_review.sql"]
    stage_sql = (seeds / "20_approval_stage.sql").read_text()
    rule_sql = (seeds / "30_approver_rule.sql").read_text()
    assert "Officers" not in stage_sql and stage_sql.count("'First approval'") == stage_sql.count("'Second approval'") == 3
    assert "'all'" not in stage_sql and stage_sql.count("'any-n',1,") == 1
    seeded_stage_ids = re.findall(r"\('([0-9a-f-]{36})','registry\.", stage_sql)
    assert len(seeded_stage_ids) == 6
    assert rule_sql.count("alex.carter") == rule_sql.count("nina.patel") == 3
    assert rule_sql.count('"admin"') == 6
    assert len(set(re.findall(r"\('([0-9a-f-]{36})'", rule_sql))) == 12, "every approver rule needs its own stable id"
    for key, order in re.findall(r"'(registry\.[a-z_]+\.[a-z-]+\.default)',(\d),'(?:First|Second) approval", stage_sql):
        assert re.search(re.escape("'" + key + "'") + rf",{order},'" + re.escape('{"user_id": "admin"}'), rule_sql)
    update = (seeds / "50_either_officer_or_admin.sql").read_text()
    assert update.count("UPDATE public.approval_stage SET mode='any-n', mode_value=1") == 1
    for stage_id in seeded_stage_ids:
        assert stage_id in update
    seeded_part, legacy_part = update.split("-- Stages created on long-lived databases", 1)
    assert "DELETE FROM" not in update and "approver_rule" not in update and "approval_policy" not in seeded_part
    # Stages that exist only on long-lived databases are renamed by policy key and exact old name: display text only.
    assert legacy_part.count("UPDATE public.approval_stage s SET name=v.new_name") == 1
    assert "mode" not in legacy_part and "stage_order" not in legacy_part and "policy_id=" in legacy_part
    # The platform's callback_secret template, carried unchanged (the seed image
    # replaces awe_meta_data and would otherwise drop it).
    template = (seeds / "40_callback_secret.sql.tpl").read_text()
    assert "${AWE_CALLBACK_SECRET_ID}" in template and "${AWE_CALLBACK_HMAC_SECRET}" in template
    others = "\n".join(p.read_text() for p in seeds.glob("*.sql") if p.name != "50_either_officer_or_admin.sql")
    assert "'expression'" not in others
    assert "UPDATE public." not in others and "DELETE FROM" not in others


def test_default_bindings_do_not_request_geographic_candidates_or_install_override():
    package = next(ROOT.glob("*-extension/src/openg2p_registry_*_extension"))
    for filename in ("zzz_default_approval_awe.sql", "zzz_farmer_reference_awe.sql"):
        sql = (package / "meta_data/register-metadata" / filename).read_text()
        assert "geo_woreda" not in sql
        assert "farmer_reference_approver_ids" not in sql
        if filename == "zzz_default_approval_awe.sql":
            assert "context_field_names=NULL" in sql
        else:
            # The Farmer-reference binding sends change_type and source for the
            # policy to test; test_verified_update_policy.py covers it.
            assert "context_field_names=EXCLUDED.context_field_names" in sql
        assert "ON CONFLICT (awe_policy_config_id) DO UPDATE" in sql
        assert "DELETE FROM" not in sql
    assert "install_geo_approval" not in (package / "app.py").read_text()
