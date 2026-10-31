"""The livestock dialogs use the OAN widgets registered in ui/staff-ui/overrides."""

import json
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
METADATA = ROOT / "livestock-extension" / "src" / "openg2p_registry_livestock_extension" / "meta_data" / "register-metadata"
REGISTER_TS = ROOT / "ui" / "staff-ui" / "overrides" / "src" / "oan" / "widgets" / "register.ts"

EVENT_TABLES = {
    "patch_ls_health_event_details_sync_ui_schema.sql": "ls_health_event_details_table",
    "patch_ls_vaccination_details_sync_ui_schema.sql": "ls_vaccination_details_table",
    "patch_ls_vital_event_details_sync_ui_schema.sql": "ls_vital_event_details_table",
    "patch_ls_breeding_details_sync_ui_schema.sql": "ls_breeding_details_table",
}


def tables(path):
    """{dialog-table widget-id: {column-key: column}} of a metadata SQL file."""
    found = {}
    text = path.read_text(encoding="utf-8")
    for match in re.finditer(r"'(\{.*?\})'(?=::jsonb|\s*[,)])", text, re.S):
        literal = match.group(1).replace("''", "'")
        if '"panels"' not in literal:
            continue

        def walk(node):
            if isinstance(node, dict):
                if node.get("widget") == "dialog-table":
                    found[node.get("widget-id")] = {c.get("column-key"): c for c in node.get("widget-data-columns", [])}
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        walk(json.loads(literal))
    return found


def assert_picker(column):
    assert column["widget"] == "oan-animal-picker"
    autofill = column["widget-autofill"]
    assert autofill["sourceSectionId"] == "livestock_animal_details_section_01"
    assert autofill["fields"] == {"age": "age", "species": "species"}


def assert_animal_columns(columns):
    assert columns["age"]["widget"] == "oan-age"
    assert columns["age"]["widget-age-from-date"] == {"baseField": "date_of_birth"}
    rule = columns["ear_tag_id"]["widget-data-validation"]
    assert re.fullmatch(rule["pattern"], "ET0000000013")
    assert not re.fullmatch(rule["pattern"], "ET000013")


@pytest.mark.parametrize("filename", sorted(EVENT_TABLES))
def test_event_dialog_ear_tag_is_the_animal_picker(filename):
    assert_picker(tables(METADATA / filename)[EVENT_TABLES[filename]]["ear_tag_id"])


def test_animal_dialog_has_live_age_and_the_ear_tag_format():
    assert_animal_columns(tables(METADATA / "patch_ls_animal_details_sync_ui_schema.sql")["ls_animal_details_table"])


def test_the_canonical_sections_use_the_same_widgets():
    found = tables(METADATA / "g2p_register_sections.sql")
    for table in EVENT_TABLES.values():
        assert_picker(found[table]["ear_tag_id"])
    assert_animal_columns(found["ls_animal_details_table"])


def test_every_oan_widget_in_the_metadata_is_registered():
    registered = set(re.findall(r"widget: '([a-z-]+)'", REGISTER_TS.read_text(encoding="utf-8")))
    used = set()
    for path in METADATA.glob("*.sql"):
        used |= set(re.findall(r'"widget": "(oan-[a-z-]+)"', path.read_text(encoding="utf-8")))
    assert used and used <= registered, used - registered
