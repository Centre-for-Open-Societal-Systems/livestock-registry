"""Animal sex is stored as the Master Data LIVESTOCK_SEX codes; MALE / FEMALE /
MIXED from before the list are still read and turned into them."""

import importlib.util
import json
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1] / "src" / "openg2p_registry_livestock_extension"
REPO = pathlib.Path(__file__).resolve().parents[2]
METADATA = ROOT / "meta_data" / "register-metadata"

SPEC = importlib.util.spec_from_file_location("lr_animal_sex", ROOT / "register_domain" / "services" / "animal_sex.py")
sex = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sex)


@pytest.mark.parametrize("value, code", [
    ("MALE", "SEX_MALE"), ("female", "SEX_FEMALE"), (" Mixed ", "SEX_MIXED"),
    ("SEX_MALE_NEUTER", "SEX_MALE_NEUTER"), ("OTHER", "OTHER"), ("", None), (None, None),
])
def test_old_codes_become_list_codes_and_others_pass_through(value, code):
    assert sex.sex_code(value) == code


def test_normalize_rewrites_only_a_supplied_value():
    record = {"gender": "FEMALE", "offspring_gender": ""}
    sex.normalize_sex(record, "gender")
    sex.normalize_sex(record, "offspring_gender")
    sex.normalize_sex(record, "missing")
    assert record == {"gender": "SEX_FEMALE", "offspring_gender": ""}


def test_a_newborn_is_never_neutered():
    assert sex.OFFSPRING_SEX_VALUES == sex.ANIMAL_SEX_VALUES - {"SEX_MALE_NEUTER", "SEX_FEMALE_NEUTER"}
    assert sex.sex_label("FEMALE") == "female" and sex.sex_label("SEX_MALE_NEUTER") == "castrated male"


def test_the_enum_holds_the_same_codes():
    enums = (ROOT / "register_domain" / "models" / "enums.py").read_text(encoding="utf-8")
    block = enums[enums.index("class GenderEnum"):enums.index("class HealthStatusEnum")]
    assert set(re.findall(r'= "(\w+)"', block)) == set(sex.ANIMAL_SEX_VALUES)


def schemas(path):
    text = path.read_text(encoding="utf-8")
    for match in re.finditer(r"'(\{.*?\})'(?=::jsonb|\s*[,)])", text, re.S):
        literal = match.group(1).replace("''", "'")
        if '"panels"' in literal:
            yield json.loads(literal)


def columns(node, key):
    if isinstance(node, dict):
        if node.get("column-key") == key:
            yield node
        for value in node.values():
            yield from columns(value, key)
    elif isinstance(node, list):
        for value in node:
            yield from columns(value, key)


@pytest.mark.parametrize("name, key", [
    ("g2p_register_sections.sql", "gender"),
    ("g2p_register_sections.sql", "offspring_gender"),
    ("patch_ls_animal_details_sync_ui_schema.sql", "gender"),
    ("patch_ls_vital_event_details_sync_ui_schema.sql", "offspring_gender"),
])
def test_sex_dropdowns_read_the_master_data_list(name, key):
    found = [column for schema in schemas(METADATA / name) for column in columns(schema, key)]
    assert found, f"{key} not found in {name}"
    for column in found:
        source = column["widget-data-source"]
        assert source["type"] == "api" and source["params"]["attribute_id"] == "LIVESTOCK_SEX"
        assert source["valueKey"] == "value_code"


def test_female_only_ear_tag_filters_use_the_list_code():
    text = (METADATA / "patch_female_only_ear_tag_filters.sql").read_text(encoding="utf-8")
    assert text.count('"value": "SEX_FEMALE"') == 2 and '"value": "FEMALE"' not in text


def test_the_migration_converts_animals_and_events_but_not_farmers():
    text = (REPO / "docker" / "db-seed" / "migrations" / "0013_animal_sex_codes.sql").read_text(encoding="utf-8")
    for table in ("g2p_register_animals", "g2p_register_history_animals", "g2p_intake_form_animals",
                  "g2p_register_vital_events", "g2p_register_history_vital_events", "g2p_intake_form_vital_events"):
        assert f"UPDATE {table} SET" in text
    assert "farmers" not in re.sub(r"^--.*$", "", text, flags=re.M)
    assert "'041a9f79-2142-548a-a15b-a4c76fc9f6f7', '76811bf6-07df-5ed4-9466-13b782f627fe'" in text
