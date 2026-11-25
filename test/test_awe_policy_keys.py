"""Guard: the AWE policy keys join across the registry database and the AWE database.

An approval is routed by policy_key across two databases seeded by different files:
  * registry: g2p_registry_awe_policy_configurations binds a register, intake form or section to a policy_key
    (meta_data/register-metadata/zzz_default_approval_awe.sql and zzz_farmer_reference_awe.sql; the reset in
    zzzzzzzzz_default_binding_reset.sql re-keys older rows to the same defaults)
  * AWE: approval_policy, approval_stage and approver_rule (awe_meta_data/)
Nothing checks the join at runtime: a binding to a key the AWE does not have leaves the change request or intake
without an approval, and the stage and rule seeds insert through a JOIN on policy_key and stage_order, so a
mistyped key or order inserts nothing. test_default_approvals.py checks the shape of each policy; this checks
that the two sides meet.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "livestock-extension/src/openg2p_registry_livestock_extension"
META = EXT / "meta_data"
AWE = EXT / "awe_meta_data"
VALUE = r"(?:'([^']*)'|NULL)"


def rows(paths, table):
    """The VALUES text of every INSERT INTO table in paths. A statement ends at a semicolon that ends a line."""
    for path in paths:
        for match in re.finditer(rf'INSERT\s+INTO\s+(?:"?public"?\.)?"?{table}"?[\s(](.*?);[ \t]*$',
                                 path.read_text(), re.S | re.I | re.M):
            yield match.group(1)


def bindings():
    """{config id: (scope, register id, intake form id, section id, policy type, policy key)} after the seed."""
    found = {}
    # The seed replays meta_data in path order, so the last row for a config id is the one that stays.
    for values in rows(sorted(META.rglob("*.sql")), "g2p_registry_awe_policy_configurations"):
        for config_id, *binding in re.findall(
                rf"\(\s*'([0-9a-f-]+)',\s*'(REGISTER|INTAKE_FORM|SECTION)',\s*{VALUE},\s*{VALUE},\s*{VALUE},"
                rf"\s*'([^']*)',\s*'([^']*)'", values):
            found[config_id] = tuple(binding)
    return found


def test_registry_bindings_join_the_awe_policies():
    seeds = sorted(META.rglob("*.sql"))
    registers = {i for values in rows(seeds, "g2p_register_definitions")
                 for i in re.findall(r"\(\s*'([^']+)'\s*,\s*'[A-Za-z]+'", values)}
    forms = {form: register for values in rows(seeds, "g2p_intake_form_definitions")
             for form, register in re.findall(r"\(\s*'([^']+)'\s*,\s*'([^']+)'", values)}
    sections = {(register, section) for values in rows(seeds, "g2p_register_sections")
                for register, section in re.findall(r"\(\s*'([^']+)'\s*,\s*'([^']+)'", values)}
    awe = sorted(AWE.glob("*.sql"))
    policies = {key: (status, artifact) for values in rows(awe, "approval_policy") for key, status, artifact in
                re.findall(r"\('[0-9a-f-]+','([^']+)',\d+,'[^']*',(?:'[^']*'|NULL),'([a-z]+)','([^']+)'", values)}
    stages = {(key, order) for values in rows(awe, "approval_stage")
              for key, order in re.findall(r"\('[0-9a-f-]+','([^']+)',(\d+),'[^'{][^']*'\)", values)}
    rules = {(key, order) for values in rows(awe, "approver_rule")
             for key, order in re.findall(r"\('[0-9a-f-]+','([^']+)',(\d+),'\{", values)}
    reset = re.findall(r"\('([0-9a-f-]+)','(change_request|intake_form)','([^']+)'\)",
                       (META / "register-metadata/zzzzzzzzz_default_binding_reset.sql").read_text())
    bound = bindings()
    assert len(registers) == 10 and len(forms) >= 2 and len(bound) >= 4 and len(reset) == 3
    assert len(policies) == 4 and stages and rules

    problems = []
    for config_id, (scope, register, form, section, policy_type, key) in sorted(bound.items()):
        if register not in registers:
            problems.append((config_id, "unknown register", register))
        if scope == "INTAKE_FORM" and forms.get(form) != register:
            problems.append((config_id, "intake form not of this register", form))
        if scope == "SECTION" and (register, section) not in sections:
            problems.append((config_id, "section not of this register", section))
        if key not in policies:
            problems.append((config_id, "no AWE policy", key))
        elif policies[key] != ("active", policy_type):
            problems.append((config_id, "policy not active or of another artifact type", key, policies[key]))
        elif not any(k == key for k, _ in stages):
            problems.append((config_id, "policy has no stage", key))
    for register, artifact, key in reset:
        if register not in registers or policies.get(key) != ("active", "registry." + artifact):
            problems.append(("reset", "no active AWE policy of this artifact type", register, key))
    problems += [("stage", "no AWE policy", key) for key, _ in stages if key not in policies]
    problems += [("rule", "no such stage", key, order) for key, order in rules if (key, order) not in stages]
    problems += [("stage", "no approver rule", key, order) for key, order in stages if (key, order) not in rules]
    assert not problems, problems
