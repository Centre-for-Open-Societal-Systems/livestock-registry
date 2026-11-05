"""Whether a verified Farmer UPDATE needs human review is policy configuration, off by default."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = next(ROOT.glob("*-extension/src/openg2p_registry_*_extension"))
SEEDS = PACKAGE / "awe_meta_data"
REGISTER_METADATA = PACKAGE / "meta_data/register-metadata"
CONFIGURATION = ROOT / "docs/refactor/configuration"
PREFIX = PACKAGE.name.removeprefix("openg2p_registry_").removesuffix("_extension") + "-farmer"
DEFAULT_KEY = f"registry.change_request.{PREFIX}.default"
SKIP_KEY = f"registry.change_request.{PREFIX}.verified-update-skips-review"
RULE = {"and": [{"==": [{"var": "change_type"}, "UPDATE"]}, {"==": [{"var": "source"}, "farmer-registry"]}]}
OFFICERS = ("alex.carter", "nina.patel")


def logic(rule, data):
    """The subset of JSONLogic the rule uses, with the library's missing-variable behaviour."""
    if not isinstance(rule, dict):
        return rule
    (op, args), = rule.items()
    if op == "var":
        return data.get(args)
    values = [logic(a, data) for a in args]
    if op == "==":
        return values[0] == values[1]
    if op == "and":
        for value in values:
            if not value:
                return value
        return values[-1]
    raise AssertionError(op)


def comment_free(text):
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("--"))


def test_the_rule_skips_only_a_verified_update():
    for change_type, source, skipped in (("UPDATE", "farmer-registry", True), ("ADD", "farmer-registry", False),
                                         ("UPDATE", "unverified", False), ("ADD", "unverified", False)):
        assert bool(logic(RULE, {"change_type": change_type, "source": source})) is skipped
    assert not logic(RULE, {}), "a request without the context keys is reviewed"
    assert not logic(RULE, {"change_type": "UPDATE"})


def test_seeded_policy_has_the_default_stages_and_the_same_skip_rule_on_each():
    sql = (SEEDS / "60_verified_update_skips_review.sql").read_text()
    code = comment_free(sql)
    assert code.count(f"'{SKIP_KEY}',1,'Farmer") == 1
    assert [json.loads(m) for m in re.findall(r"CAST\('(\{.*?\})' AS json\)", code)] == [RULE]
    assert "'any-n',1," in code and "'block'" in code
    for officer in OFFICERS:
        assert code.count(officer) == 1
    assert code.count('"admin"') == 2
    stages = re.findall(rf"\('[0-9a-f-]{{36}}','{re.escape(SKIP_KEY)}',(\d),'(?:First|Second) approval", code)
    assert stages == ["1", "2"]
    # Insert-only: an active policy version is immutable and seeds never delete.
    assert not re.search(r"(?m)^\s*(UPDATE|DELETE)\b|\bNOT IN\b", code)
    assert code.count("ON CONFLICT") == 3 and code.count("WHERE NOT EXISTS") == 2
    ids = re.findall(r"\('([0-9a-f-]{36})'", code)
    assert len(ids) == len(set(ids)) == 7


def test_default_farmer_reference_stages_have_no_skip_rule_and_nothing_uses_the_new_key():
    stage_sql = comment_free((SEEDS / "20_approval_stage.sql").read_text())
    assert "skip_if" in stage_sql and "'null','block'" in stage_sql
    assert "json_logic" not in stage_sql and '"var"' not in stage_sql
    for path in list(SEEDS.glob("*.sql")) + list(REGISTER_METADATA.glob("*.sql")):
        if path.name != "60_verified_update_skips_review.sql":
            assert SKIP_KEY not in comment_free(path.read_text()), path.name
    binding = comment_free((REGISTER_METADATA / "zzz_farmer_reference_awe.sql").read_text())
    assert f"'{DEFAULT_KEY}'" in binding, "shipped setting: two human stages for every change"


def test_binding_sends_the_two_context_keys_and_the_reset_leaves_it_alone():
    binding_sql = (REGISTER_METADATA / "zzz_farmer_reference_awe.sql").read_text()
    code = comment_free(binding_sql)
    assert "'[\"change_type\", \"source\"]'" in code
    assert "context_field_names=EXCLUDED.context_field_names" in code and "context_field_names=NULL" not in code
    assert SKIP_KEY in binding_sql, "the switch must name the alternative it flips to"
    binding_id = re.search(r"VALUES \('([0-9a-f-]{36})','SECTION'", code).group(1)
    for name in ("00_archive_approval_bindings.sql", "zzzzzzzzz_default_binding_reset.sql"):
        assert f"c.awe_policy_config_id <> '{binding_id}'" in (REGISTER_METADATA / name).read_text(), name
    reset = (REGISTER_METADATA / "zzzzzzzzz_default_binding_reset.sql").read_text()
    assert reset.count(f"c.awe_policy_config_id <> '{binding_id}'") == 2


def test_documented_policies_match_the_seeds():
    shipped = {p["policy_key"]: p for p in json.loads((CONFIGURATION / "default-awe-policies.json").read_text())}
    assert json.loads((CONFIGURATION / "farmer-reference-awe-policy.json").read_text()) == shipped[DEFAULT_KEY]
    skip = json.loads((CONFIGURATION / "farmer-reference-verified-update-skips-review.json").read_text())
    assert skip["policy_key"] == SKIP_KEY
    assert [s["skip_if"] for s in skip["stages"]] == [RULE, RULE]
    for stage, base in zip(skip["stages"], shipped[DEFAULT_KEY]["stages"]):
        assert {k: v for k, v in stage.items() if k != "skip_if"} == base
