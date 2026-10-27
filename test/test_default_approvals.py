"""The requested defaults are native two-stage policies, not auto-approval."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_all_domain_and_reference_policies_use_the_upstream_default_stages():
    policies = json.loads((ROOT / "docs/refactor/configuration/default-awe-policies.json").read_text())
    assert len(policies) == 3
    assert len({p["policy_key"] for p in policies}) == 3
    for policy in policies:
        assert policy["policy_key"].endswith(".default")
        assert policy["forbid_self_approval"] is False
        assert policy["forbid_repeat_approvers"] is False
        assert [stage["stage_order"] for stage in policy["stages"]] == [1, 2]
        for stage, reviewer in zip(policy["stages"], ("alex.carter", "nina.patel")):
            assert stage["mode"] == "all"
            assert stage["on_empty"] == "block"
            assert stage["rules"] == [{"rule_type": "user", "rule_value": {"user_id": reviewer},
                                       "kind": "approver", "required": False}]


def test_default_bindings_do_not_request_geographic_candidates_or_install_override():
    package = next(ROOT.glob("*-extension/src/openg2p_registry_*_extension"))
    for filename in ("zzz_default_approval_awe.sql", "zzz_farmer_reference_awe.sql"):
        sql = (package / "meta_data/register-metadata" / filename).read_text()
        assert "geo_woreda" not in sql
        assert "farmer_reference_approver_ids" not in sql
        assert "context_field_names=NULL" in sql
        assert "ON CONFLICT (awe_policy_config_id) DO UPDATE" in sql
        assert "DELETE FROM" not in sql
    assert "install_geo_approval" not in (package / "app.py").read_text()
    seeds = package / "awe_meta_data"
    assert sorted(p.name for p in seeds.iterdir() if p.is_file()) == [
        "10_approval_policy.sql", "20_approval_stage.sql", "30_approver_rule.sql"]
    sql = "\n".join(p.read_text() for p in seeds.glob("*.sql"))
    assert "'expression'" not in sql
    assert "UPDATE public." not in sql and "DELETE FROM" not in sql
    assert sql.count('alex.carter') == sql.count('nina.patel') == 3
