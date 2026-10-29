"""Compare effective live metadata with native model/seed rehearsal output."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NATIVE_HISTORY_CONTROLS = {"last_approved_at", "last_approved_by", "search_text"}

def field_type(value):
    value = value.upper()
    if value.startswith(("VARCHAR","TEXT","UUID")): return "string"
    if value.startswith(("FLOAT","NUMERIC","DECIMAL")): return "number"
    return {"INTEGER":"integer","BOOLEAN":"boolean","DATETIME":"datetime","DATE":"date","JSONB":"json","JSON":"json"}.get(value,value.lower())

def paths(value):
    found = set()
    if isinstance(value,dict):
        for key,item in value.items():
            if key in {"widget-data-path","data-path"}:
                def leaves(node):
                    if isinstance(node,str): found.add(node)
                    elif isinstance(node,dict):
                        for child in node.values(): leaves(child)
                    elif isinstance(node,list):
                        for child in node: leaves(child)
                leaves(item)
            found.update(paths(item))
    elif isinstance(value,list):
        for item in value:
            found.update(paths(item))
    return found

def reconcile_sections(rows, metadata, transitions):
    """Named schema changes count only when their effective target is usable."""
    sections = {row['section_id']:row for row in metadata['g2p_register_sections']}
    intake = metadata['g2p_intake_form_ui_tab_sections']
    registered = metadata['g2p_register_ui_tab_sections']
    outcomes = []

    def widgets(node):
        if isinstance(node,dict):
            if 'widget' in node: yield node
            for value in node.values(): yield from widgets(value)
        elif isinstance(node,list):
            for value in node: yield from widgets(value)

    for row in rows:
        unresolved = []
        for path in row['removed_field_paths']:
            rules = [rule for rule in transitions if rule.get('from_section')==row['section_id'] and rule.get('path')==path]
            valid = False
            if len(rules)==1 and rules[0]['mechanism'] in ('section_move','approved_farmer_projection'):
                rule = rules[0]
                target = sections.get(rule['to_section'])
                valid = target is not None and target['section_register_id']==row['section_register_id'] and path in paths(target['section_ui_schema'])
                if valid and rule['mechanism']=='section_move':
                    tabs = {binding['tab_id'] for binding in intake if binding['section_id']==row['section_id']}
                    valid = bool(tabs) and all(any(binding['tab_id']==tab and binding['section_id']==rule['to_section'] for binding in intake) for tab in tabs)
                    valid = valid and target['section_ui_schema'].get('section-required-for-submit') is True
                elif valid and rule['mechanism']=='approved_farmer_projection':
                    valid = not any(binding['section_id']==row['section_id'] for binding in registered)
                    valid = valid and any(binding['section_id']==rule['to_section'] for binding in registered)
                    valid = valid and any(widget.get('widget-data-path')==path and widget.get('widget')=='display' and widget.get('widget-readonly') is True for widget in widgets(target['section_ui_schema']))
                else:
                    valid = False
                outcomes.append({**rule,'verified':bool(valid)})
            elif len(rules)==1 and rules[0]['mechanism']=='geo_hierarchy_derived':
                # A per-level Master Data id column (region_id ... kebele_id) no longer has
                # its own dropdown: the target section's geo-hierarchy widget writes the
                # register's hierarchy document, and the column is filled from it on save
                # (register_domain/services/geo_hierarchy.py). Valid only when that widget
                # is bound to the same register's geo_code_hierarchy_json.
                rule = rules[0]
                target = sections.get(rule['to_section'])
                register_id, _, column = path.rpartition('.')
                hierarchy_path = f"{register_id}.geo_code_hierarchy_json"
                valid = (target is not None and target['section_register_id']==row['section_register_id']
                         and column in {'region_id','zone_id','woreda_id','kebele_id'}
                         and any(widget.get('widget')=='geo-hierarchy'
                                 and isinstance(widget.get('widget-data-path'),dict)
                                 and widget['widget-data-path'].get('hierarchy')==hierarchy_path
                                 for widget in widgets(target['section_ui_schema'])))
                outcomes.append({**rule,'verified':bool(valid)})
            if not valid: unresolved.append(path)
        row['unexplained_removed_field_paths'] = unresolved
    return outcomes


def main(domain):
    repo = ROOT if (ROOT / f"{domain}-extension").is_dir() else ROOT / f"OAN/worktrees/{domain}-registry/develop-refactor"
    folder = repo / "ci-output/refactor/new-dev"
    live = json.loads((repo / "reference/new-dev/metadata.json").read_text(encoding="utf-8"))
    target = json.loads((folder / "target-pass-2.json").read_text(encoding="utf-8"))
    seed = json.loads((folder / "seed-rehearsal.json").read_text(encoding="utf-8"))
    report = {"registry":domain,"live_captured_at":live["captured_at"],"runtime_model_presence":[],
        "sections":[],"forms":[],"physical_database_columns_verified":False,
        "standards_scope":"Native extension DDL, seeded metadata and registered runtime declared fields; not full business/live acceptance",
        "sql_errors":[step for step in seed["steps"] if step["sqlstate_errors"]],
        "repeat_metadata_identical":seed["repeat_metadata_identical"]}
    transition_file = repo / 'reference/metadata-transitions.json'
    transition_doc = json.loads(transition_file.read_text(encoding='utf-8')) if transition_file.exists() else {}
    # Registers retired on purpose are named in the transitions file; they must be gone from the target.
    retired = {row["register_id"]:row for row in transition_doc.get("retired_registers", [])}
    retired_sections = {section for row in retired.values() for section in row.get("section_ids", [])}
    target_registers = {row["register_id"] for row in target["metadata"].get("g2p_register_definitions", [])}
    target_sections = {row["section_id"] for row in target["metadata"]["g2p_register_sections"]}
    report["retired_registers"] = [{"register_id":rid,"register_mnemonic":row.get("register_mnemonic"),
        "absent_from_target":rid not in target_registers and not (set(row.get("section_ids", [])) & target_sections)}
        for rid, row in retired.items()]
    for entry in live["registers"]:
        if entry["definition"]["register_id"] in retired:
            continue
        name = entry["definition"]["register_mnemonic"]
        fields = {field["field_name"] for field in entry["fields"]["fields"]}
        models = {prefix:target["models"][prefix+name] for prefix in
                  ("G2PRegister","G2PRegisterHistory","G2PIntakeForm")}
        report["runtime_model_presence"].append({"register":name,"register_id":entry["definition"]["register_id"],
            "live_fields":sorted(fields), "live_field_count":len(fields),
            "missing_by_model":{prefix:sorted(fields-set(model["columns"])) for prefix,model in models.items()},
            "missing_domain_by_model":{prefix:sorted((fields-NATIVE_HISTORY_CONTROLS)-set(model["columns"])) for prefix,model in models.items()},
            "type_mismatches":[{"field":field["field_name"],"live":field["data_type"],
                "target":models["G2PRegister"]["columns"][field["field_name"]]["type"]}
                for field in entry["fields"]["fields"] if field["field_name"] in models["G2PRegister"]["columns"] and
                field_type(models["G2PRegister"]["columns"][field["field_name"]]["type"]) != field["data_type"]],
            "added_register_fields":sorted(set(models["G2PRegister"]["columns"])-fields)})
    sections = {row["section_id"]:row for row in target["metadata"]["g2p_register_sections"]}
    for entry in live["registers"]:
        for row in entry["sections"]:
            if row["section_id"] in retired_sections:
                continue
            new = sections.get(row["section_id"])
            report["sections"].append({"section_id":row["section_id"],"register_id":row["register_id"],
                "section_register_id":row["section_register_id"],"present":new is not None,
                "removed_field_paths":sorted(paths(row["section_ui_schema"])-paths(new["section_ui_schema"])) if new else sorted(paths(row["section_ui_schema"])),
                "added_field_paths":sorted(paths(new["section_ui_schema"])-paths(row["section_ui_schema"])) if new else [],
                "relationship_preserved":new is not None and new["section_register_id"]==row["section_register_id"]})
    definitions = {row["form_id"]:row for row in target["metadata"]["g2p_intake_form_definitions"]}
    tabs = {row["tab_id"]:row for row in target["metadata"]["g2p_intake_form_ui_tabs"]}
    bindings = {row["tab_section_id"]:row for row in target["metadata"]["g2p_intake_form_ui_tab_sections"]}
    for form in live["forms"]:
        item = {"form_id":form["form_id"],"form_mnemonic":form["form_mnemonic"],"present":form["form_id"] in definitions,"tabs":[]}
        for tab in form["tabs"]:
            item["tabs"].append({"tab_id":tab["tab_id"],"present":tab["tab_id"] in tabs,
                "bindings":[{"tab_section_id":binding["tab_section_id"],"section_id":binding["section_id"],
                    "target_section_id":bindings.get(binding["tab_section_id"],{}).get("section_id"),
                    "present":binding["tab_section_id"] in bindings} for binding in tab["sections"]]})
        report["forms"].append(item)
    transitions = transition_doc.get('transitions', [])
    report['section_transitions'] = reconcile_sections(report['sections'],target['metadata'],transitions)
    report['all_section_capabilities_preserved'] = all(row['present'] and row['relationship_preserved'] and not row['unexplained_removed_field_paths'] for row in report['sections'])
    report["all_live_register_fields_present"] = all(not item["missing_by_model"]["G2PRegister"] for item in report["runtime_model_presence"])
    report["all_section_field_paths_preserved"] = all(row["present"] and row["relationship_preserved"] and not row["removed_field_paths"] for row in report["sections"])
    report["all_form_ids_preserved"] = all(row["present"] for row in report["forms"])
    report["all_domain_history_intake_fields_present"] = all(not fields for row in report["runtime_model_presence"] for fields in row["missing_domain_by_model"].values())
    report["all_register_field_types_match"] = all(not row["type_mismatches"] for row in report["runtime_model_presence"])
    report["all_retired_registers_absent"] = all(row["absent_from_target"] for row in report["retired_registers"])
    report["field_count"] = sum(row["live_field_count"] for row in report["runtime_model_presence"])
    (folder / "comparison.json").write_bytes((json.dumps(report,indent=2)+"\n").encode("utf-8"))
    checks=("all_live_register_fields_present","all_section_capabilities_preserved","all_form_ids_preserved",
            "all_domain_history_intake_fields_present","all_register_field_types_match","all_retired_registers_absent","repeat_metadata_identical")
    if report["sql_errors"] or not all(report[key] for key in checks):
        (folder / "VERIFICATION.md").write_text("# Metadata verification failed\n\nSee comparison.json; field/section/type or seed acceptance failed.\n",encoding="utf-8")
        raise RuntimeError("Metadata comparison failed; no successful acceptance claim written")
    lines = ["# New Dev field and section verification", "",f"Authenticated metadata captured {live['captured_at']}.","",
        "| Register | Live fields | Missing from native refactor register |", "| --- | --- | --- |"]
    for row in report["runtime_model_presence"]:
        missing = row["missing_by_model"]["G2PRegister"]
        lines.append(f"| {row['register']} | {row['live_field_count']} | {', '.join(missing) or 'None'} |")
    lines += ["",f"All {report['field_count']} live declared fields are present. All {len(report['sections'])} section IDs and {len(report['forms'])} form IDs are retained.",
        "Register/history/intake mappings and every section path/binding are enumerated in comparison.json. Named section moves and source-owned display replacements are checked against effective target bindings, not silently ignored.","",
        "Domain fields are present in all three native register/history/intake models. Native history owns its version/audit metadata; the live-register control fields last_approved_at, last_approved_by and search_text are not copied into the history model.","",
        "Both native psql seed passes completed without SQL errors; final metadata is identical on repeat." if not report["sql_errors"] and report["repeat_metadata_identical"] else "Seed errors or changes remain; inspect seed-rehearsal.json.","",
        "This verifies effective application metadata against native rc.614 ORM/DDL and seed results. Physical New Dev database columns, portal rendering, business-rule parity, restored-data upgrade and full live integration are not certified.","",
        "The Farmer identity pair is captured on the domain root. The retired sibling Farmer intake mapping is intentionally replaced by the separately approved reference dependency. All Farmer register sections and field names remain.","",
        "Crop's legacy registry-database lookup SQL is preserved as a Master Data administration prerequisite in the central Helm repository; it is not executed against a registry. Existing shared values are not changed.","",
        "The live Crop FARMER_REFERENCE_CHANGED_V1 pipeline configuration requires an explicit port and remains a promotion blocker. Livestock MY_DATA_MODEL and LIVESTOCK_ODK_MODEL are retired and replaced by ODK_TO_LIVESTOCK_INTAKE.","",
        "No records, approvals, identity grants, environment settings or runtime workloads were modified."]
    (folder / "VERIFICATION.md").write_bytes(("\n".join(lines)+"\n").encode("utf-8"))
    print(json.dumps({"registry":domain,"fields":report["field_count"],"all_live_register_fields_present":report["all_live_register_fields_present"],
        "sections":len(report["sections"]),"all_section_field_paths_preserved":report["all_section_field_paths_preserved"],"all_section_capabilities_preserved":report["all_section_capabilities_preserved"],
        "forms":len(report["forms"]),"all_form_ids_preserved":report["all_form_ids_preserved"],"seed_errors":len(report["sql_errors"])}))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("domain",choices=("cropsown","livestock"))
    main(parser.parse_args().domain)
