"""The livestock event and status dropdowns read their values from Master Data lists."""

import json
import pathlib
import re

import pytest

METADATA = (pathlib.Path(__file__).resolve().parents[1]
            / "src" / "openg2p_registry_livestock_extension" / "meta_data" / "register-metadata")

EXPECTED = {
    "animal_details": {"health_status": "LIVESTOCK_HEALTH_STATUS", "vaccination_status": "LIVESTOCK_VACCINATION_STATUS"},
    "health_event_details": {"event_type": "LIVESTOCK_HEALTH_EVENT_TYPE", "location": "LIVESTOCK_EVENT_LOCATION"},
    "vital_event_details": {"event_type": "LIVESTOCK_VITAL_EVENT_TYPE", "cause": "LIVESTOCK_CAUSE_OF_DEATH",
                            "location": "LIVESTOCK_EVENT_LOCATION"},
    "breeding_details": {"event_type": "LIVESTOCK_BREEDING_METHOD", "outcome": "LIVESTOCK_BREEDING_OUTCOME",
                         "location": "LIVESTOCK_EVENT_LOCATION"},
    "retagging_details": {"reason": "LIVESTOCK_RETAG_REASON"},
}
FILES = {
    "animal_details": "patch_ls_animal_details_sync_ui_schema.sql",
    "health_event_details": "patch_ls_health_event_details_sync_ui_schema.sql",
    "vital_event_details": "patch_ls_vital_event_details_sync_ui_schema.sql",
    "breeding_details": "patch_ls_breeding_details_sync_ui_schema.sql",
    "retagging_details": "patch_ls_retagging_details_section.sql",
}


def schemas(path):
    """The section UI schemas (JSON literals with panels) in a metadata SQL file."""
    text = path.read_text(encoding="utf-8")
    for match in re.finditer(r"'(\{.*?\})'(?=::jsonb|\s*[,)])", text, re.S):
        literal = match.group(1).replace("''", "'")
        if '"panels"' in literal:
            yield json.loads(literal)


def sources(schema):
    found = {}

    def walk(node):
        if isinstance(node, dict):
            key = node.get("column-key") or node.get("widget-id")
            if key and isinstance(node.get("widget-data-source"), dict):
                found.setdefault(key, []).append(node["widget-data-source"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(schema)
    return found


def assert_from_master_data(found, expected):
    for field, attribute_id in expected.items():
        assert found.get(field), f"{field} has no dropdown"
        for source in found[field]:
            assert source.get("type") == "api", f"{field} is still {source.get('type')}"
            assert source.get("params", {}).get("attribute_id") == attribute_id
            # value_id carries the list prefix; the stored value is the code.
            assert source.get("valueKey") == "value_code"


@pytest.mark.parametrize("section", sorted(EXPECTED))
def test_the_section_patch_reads_its_dropdowns_from_master_data(section):
    found = {}
    for schema in schemas(METADATA / FILES[section]):
        for field, values in sources(schema).items():
            found.setdefault(field, []).extend(values)
    assert_from_master_data(found, EXPECTED[section])


def test_the_canonical_sections_read_the_same_lists():
    text = (METADATA / "g2p_register_sections.sql").read_text(encoding="utf-8")
    for section, expected in EXPECTED.items():
        literal = re.search(r"livestock_%s_section_0\d.*?'(\{.*?\})'(?=::jsonb|\s*[,)])" % section, text, re.S)
        assert literal, f"{section} not found"
        assert_from_master_data(sources(json.loads(literal.group(1).replace("''", "'"))), expected)
