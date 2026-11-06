"""Livestock intake and change requests take one approval by a Woreda Approver, from policy configuration only."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = next(ROOT.glob("*-extension/src/openg2p_registry_*_extension"))
SEED = PACKAGE / "awe_meta_data/70_woreda_approval.sql"
REGISTER_METADATA = PACKAGE / "meta_data/register-metadata"
INTAKE, CHANGE = "registry.intake_form.livestock.woreda", "registry.change_request.livestock.woreda"
ROLE = {"role": "Woreda Approver", "client": "livestock-registry-staff-portal"}
ADMIN = {"user_id": "admin"}


def code():
    return "\n".join(line for line in SEED.read_text().splitlines() if not line.lstrip().startswith("--"))


def test_each_policy_has_one_stage_of_one_decision():
    sql = code()
    for key in (INTAKE, CHANGE):
        assert re.findall(rf"\('[0-9a-f-]{{36}}','{re.escape(key)}',(\d),'Woreda approval'\)", sql) == ["1"]
    assert "'any-n',1," in sql and "'block'" in sql


def test_approvers_are_the_role_and_admin_and_nothing_routes_by_place():
    sql = code()
    rules = re.findall(r"\('[0-9a-f-]{36}','(registry\.[a-z_.]+)',1,'(role|user)','(\{.*?\})'\)", sql)
    assert sorted((key, kind) for key, kind, _ in rules) == [
        (CHANGE, "role"), (CHANGE, "user"), (INTAKE, "role"), (INTAKE, "user")]
    for _, kind, value in rules:
        assert json.loads(value) == (ROLE if kind == "role" else ADMIN)
    assert "geo_" not in sql and "'expression'" not in sql


def test_seed_only_inserts_and_every_row_has_its_own_id():
    sql = code()
    assert not re.search(r"(?m)^\s*(UPDATE|DELETE)\b", sql)
    ids = re.findall(r"\('([0-9a-f-]{36})'", sql)
    assert len(ids) == 8 and len(set(ids)) == 8


def test_the_bindings_name_the_woreda_policies_and_leave_the_farmer_reference_alone():
    for name in ("zzz_default_approval_awe.sql", "zzzzzzzzz_default_binding_reset.sql"):
        sql = (REGISTER_METADATA / name).read_text()
        assert f"'{INTAKE}'" in sql and f"'{CHANGE}'" in sql
        assert "'registry.intake_form.livestock.default'" not in sql
        assert "'registry.change_request.livestock.default'" not in sql
        assert "'registry.change_request.livestock-farmer.default'" in sql


def test_the_declared_policies_match_the_seed():
    policies = json.loads((ROOT / "docs/refactor/configuration/woreda-awe-policies.json").read_text())
    assert sorted(p["policy_key"] for p in policies) == [CHANGE, INTAKE]
    for policy in policies:
        (stage,) = policy["stages"]
        assert (stage["stage_order"], stage["mode"], stage["mode_value"], stage["on_empty"]) == (1, "any-n", 1, "block")
        assert [rule["rule_value"] for rule in stage["rules"]] == [ROLE, ADMIN]
