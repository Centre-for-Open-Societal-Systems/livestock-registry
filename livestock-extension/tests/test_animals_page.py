"""The Animals page (ui/staff-ui overrides) stays in step with the metadata: the
fields a bulk update sends are the Livestock Details section's columns, and the
register, tab and section it names exist."""

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
OVERRIDES = ROOT / "ui" / "staff-ui" / "overrides" / "src"
ANIMALS_TS = OVERRIDES / "oan" / "animals" / "animals.ts"
METADATA = ROOT / "livestock-extension" / "src" / "openg2p_registry_livestock_extension" / "meta_data" / "register-metadata"


def constant(name):
    return re.search(rf"export const {name} = '([^']+)'", ANIMALS_TS.read_text(encoding="utf-8")).group(1)


def animal_section_columns():
    text = (METADATA / "patch_ls_animal_details_sync_ui_schema.sql").read_text(encoding="utf-8")
    for match in re.finditer(r"'(\{.*?\})'(?=::jsonb|\s*[,)])", text, re.S):
        literal = match.group(1).replace("''", "'")
        if '"ls_animal_details_table"' in literal:
            found = []

            def walk(node):
                if isinstance(node, dict):
                    if node.get("widget-id") == "ls_animal_details_table":
                        found.extend(c["column-key"] for c in node["widget-data-columns"])
                    for value in node.values():
                        walk(value)
                elif isinstance(node, list):
                    for value in node:
                        walk(value)

            walk(json.loads(literal))
            return found
    raise AssertionError("Livestock Details table not found")


def test_bulk_update_sends_exactly_the_section_columns():
    text = ANIMALS_TS.read_text(encoding="utf-8")
    fields = re.findall(r"'([a-z_]+)'", text[text.index("const SECTION_FIELDS"):text.index("];", text.index("const SECTION_FIELDS"))])
    assert set(fields) - {"internal_record_id", "link_internal_record_id"} == set(animal_section_columns())


def test_register_tab_and_section_ids_match_the_metadata():
    definitions = (METADATA / "g2p_register_definitions.sql").read_text(encoding="utf-8")
    assert re.search(rf"'{constant('LIVESTOCK_REGISTER')}'[^\n]*'Livestock'", definitions)
    assert re.search(rf"'{constant('ANIMAL_REGISTER')}'[^\n]*'Animal'", definitions)
    tabs = (METADATA / "g2p_register_ui_tab_sections.sql").read_text(encoding="utf-8")
    assert f"'{constant('ANIMAL_TAB')}','{constant('ANIMAL_SECTION')}'" in tabs


def test_page_is_guarded_and_linked_from_the_header():
    layout = (OVERRIDES / "app" / "[locale]" / "animals" / "layout.tsx").read_text(encoding="utf-8")
    assert "RequireAction action={REGISTER_ACTIONS.view}" in layout
    header = (OVERRIDES / "components" / "layout" / "Header.tsx").read_text(encoding="utf-8")
    assert "<Can action={REGISTER_ACTIONS.view}>" in header and "/animals" in header
