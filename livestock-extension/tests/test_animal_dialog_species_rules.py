"""The Livestock Details and Vital Event dialogs follow the animal's species, and
the server keeps the same rules: Sex as before the list moved to Master Data
(no castrated male or female neuter), and no event for a dead animal."""

import asyncio
import importlib
import json
import os
import pathlib
import re
from unittest.mock import AsyncMock, patch

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
META = ROOT / "livestock-extension" / "src" / "openg2p_registry_livestock_extension" / "meta_data" / "register-metadata"
PATCH = META / "zzzzzzzzz_animal_dialog_species_rules.sql"
WIDGETS = ROOT / "ui" / "staff-ui" / "overrides" / "src" / "oan" / "widgets"

RULES = "species_rules"


def has(setting):
    return {"field": RULES, "operator": "contains", "value": setting}


def patches():
    """{table widget-id: {column-key: patch}} of the SQL file."""
    sql = PATCH.read_text(encoding="utf-8")
    found = {}
    for table, literal, extra in re.findall(r"'(ls_[a-z_]+_table)', '(\{.*?\})'::jsonb, '(\[.*?\])'::jsonb", sql, re.S):
        found[table] = json.loads(literal)
        found[table + ":extra"] = json.loads(extra)
    return found


def actions(column):
    return {a["action"]: a["condition"] for a in column["widget-data-options"]["actions"]}


def test_it_runs_after_the_field_order_patch_and_before_the_required_row_overlay():
    files = sorted(p.name for p in META.glob("*.sql"))
    assert files.index("zzzzzzzzz_animal_dialog_field_order.sql") < files.index(PATCH.name)
    assert files.index(PATCH.name) < files.index("zzzzzzzzzz_required_animal_row.sql")
    assert "WHERE section_id = 'livestock_animal_details_section_01'" in PATCH.read_text(encoding="utf-8")


def test_species_hides_the_values_kept_only_for_older_records():
    species = patches()["ls_animal_details_table"]["species"]
    assert species["widget"] == "select"
    assert species["widget-hide-values"] == ["EQUINES", "OTHER"]


def test_species_copies_its_settings_into_a_hidden_column_the_rules_read():
    species = patches()["ls_animal_details_table"]["species"]
    assert species["widget-copy-attributes"] == {"column": RULES, "attributes": ["requires_ear_tag", "is_flock_species"]}
    (helper,) = patches()["ls_animal_details_table:extra"]
    assert helper["column-key"] == RULES and helper["column-visible-in-table"] is False
    assert "widget-data-path" not in helper and helper["widget-required"] is False
    # Always hidden: never shown in the dialog, never sent with the row.
    assert actions(helper) == {"hide": {"field": RULES, "operator": "notEquals", "value": "__shown_never__"}}
    assert patches()["ls_vital_event_details_table:extra"] == []


def test_breed_offers_the_chosen_species_breeds_and_the_types_only_without_any():
    for table in ("ls_animal_details_table", "ls_vital_event_details_table"):
        column = patches()[table]["breed" if table == "ls_animal_details_table" else "offspring_breed"]
        assert column["widget"] == "select"
        assert column["widget-filter-by"] == {"field": "species", "attribute": "species", "fallback": "unattributed"}


def test_sex_offers_mixed_only_for_a_species_without_an_ear_tag():
    rule = patches()["ls_animal_details_table"]["gender"]["widget-options-by"]
    assert rule["field"] == "species" and rule["list"] == "LIVESTOCK_SPECIES" and rule["attribute"] == "requires_ear_tag"
    assert rule["values"] == {"true": ["SEX_MALE", "SEX_FEMALE"], "false": ["SEX_MALE", "SEX_FEMALE", "SEX_MIXED"]}
    assert rule["default"] == ["SEX_MALE", "SEX_FEMALE"]
    offspring = patches()["ls_vital_event_details_table"]["offspring_gender"]["widget-options-by"]
    assert offspring == {"default": ["SEX_MALE", "SEX_FEMALE", "SEX_MIXED"]}


def test_identifier_head_count_and_date_of_birth_follow_the_species():
    animal = patches()["ls_animal_details_table"]
    assert actions(animal["ear_tag_id"]) == {"hide": has("requires_ear_tag=false"), "require": has("requires_ear_tag=true")}
    secondary = actions(animal["secondary_identifier"])
    assert secondary == {"show": has("requires_ear_tag=false"), "require": has("requires_ear_tag=false")}
    quantity = actions(animal["quantity"])
    assert quantity == {"show": has("is_flock_species=true"), "require": has("is_flock_species=true")}
    assert actions(animal["date_of_birth"]) == {"require": has("is_flock_species=false")}
    # Required only through the rules, so a hidden field is never asked for.
    assert all(animal[key]["widget-required"] is False
               for key in ("ear_tag_id", "secondary_identifier", "quantity", "date_of_birth"))


def test_the_rules_use_only_operators_the_platform_evaluates():
    sql = PATCH.read_text(encoding="utf-8")
    used = set(re.findall(r'"operator": "([a-zA-Z]+)"', sql))
    assert used <= {"equals", "notEquals", "empty", "notEmpty", "contains", "notContains"}


def test_a_stored_row_without_the_hidden_column_is_asked_for_nothing_more():
    required_fields = pytest.importorskip(os.environ.get("REGISTRY_EXTENSION_MODULE", "openg2p_registry_livestock_extension")
                                          + ".required_fields")
    animal = patches()["ls_animal_details_table"]
    for key in ("ear_tag_id", "secondary_identifier", "quantity", "date_of_birth"):
        visible, required = required_fields.widget_state(animal[key], {"species": "POULTRY"})
        assert required is False, key
    poultry = {"species_rules": "requires_ear_tag=false is_flock_species=true"}
    assert required_fields.widget_state(animal["ear_tag_id"], poultry) == (False, False)
    assert required_fields.widget_state(animal["quantity"], poultry) == (True, True)
    cow = {"species_rules": "requires_ear_tag=true is_flock_species=false"}
    assert required_fields.widget_state(animal["ear_tag_id"], cow) == (True, True)
    assert required_fields.widget_state(animal["secondary_identifier"], cow) == (False, False)
    assert required_fields.widget_state(animal["date_of_birth"], cow) == (True, True)


def test_the_widget_is_registered_as_select_and_under_its_own_names():
    register = (WIDGETS / "register.ts").read_text(encoding="utf-8")
    # "select" itself, so the dialog table keeps showing a cell's label rather than its code.
    assert "widget: 'select', component: OanSelectWidget" in register
    assert "widget: 'oan-filtered-select', component: FilteredSelectWidget" in register
    assert "widget: 'oan-vaccine-select', component: FilteredSelectWidget" in register
    source = (WIDGETS / "FilteredSelectWidget.tsx").read_text(encoding="utf-8")
    assert "export function OanSelectWidget" in source
    for key in ("widget-filter-by", "widget-options-by", "widget-hide-values", "widget-copy-attributes"):
        assert f"config['{key}']" in source


def test_every_patched_dropdown_stays_a_select_and_the_vaccine_becomes_one():
    found = patches()
    for table, key in [("ls_animal_details_table", "species"), ("ls_animal_details_table", "breed"),
                       ("ls_animal_details_table", "gender"), ("ls_vital_event_details_table", "offspring_gender"),
                       ("ls_vital_event_details_table", "offspring_breed"), ("ls_vaccination_details_table", "vaccine_type")]:
        assert found[table][key]["widget"] == "select", (table, key)


def test_the_picker_says_when_the_animals_could_not_be_loaded():
    source = (WIDGETS / "AnimalPickerWidget.tsx").read_text(encoding="utf-8")
    assert "setFailed(true)" in source and "could not be loaded" in source


# The server --------------------------------------------------------------------

pytest.importorskip("openg2p_registry_core")

PACKAGE = os.environ.get("REGISTRY_EXTENSION_MODULE", "openg2p_registry_livestock_extension")
SERVICES = PACKAGE + ".register_domain.services."
utils = importlib.import_module(SERVICES + "domain_validation_utils")
animal = importlib.import_module(SERVICES + "g2p_register_domain_service_animal")
from openg2p_registry_core.errors import G2PRegistryException  # noqa: E402

gender_rule = animal.G2PRegisterDomainServiceAnimal._validate_gender_for_species


@pytest.mark.parametrize("sex, requires_ear_tag", [
    ("SEX_MALE", True), ("SEX_FEMALE", True), ("MALE", True),
    ("SEX_MIXED", False), ("SEX_FEMALE", False),
])
def test_male_female_and_mixed_for_a_flock_are_recorded(sex, requires_ear_tag):
    gender_rule(None, {"gender": sex}, requires_ear_tag)


@pytest.mark.parametrize("sex, words", [
    ("SEX_MALE_NEUTER", "castrated male"), ("SEX_FEMALE_NEUTER", "female neuter"), ("OTHER", "OTHER"),
])
def test_castrated_male_female_neuter_and_unknown_codes_are_refused(sex, words):
    with pytest.raises(G2PRegistryException, match=words):
        gender_rule(None, {"gender": sex}, True)


def test_mixed_is_refused_for_an_ear_tagged_species():
    with pytest.raises(G2PRegistryException, match="choose Male or Female"):
        gender_rule(None, {"gender": "SEX_MIXED"}, True)


def run(coro):
    return asyncio.run(coro)


def test_an_event_for_a_dead_animal_is_refused():
    with patch.object(utils, "_recorded_animal_value", AsyncMock(return_value="DECEASED")) as lookup:
        with pytest.raises(G2PRegistryException, match="ET0000000013' is deceased; a vaccination"):
            run(utils.validate_animal_not_deceased({"ear_tag_id": "et0000000013"}, "vaccination"))
    lookup.assert_awaited_once_with("ET0000000013", "health_status")


@pytest.mark.parametrize("status", ["HEALTHY", "SICK", None])
def test_an_event_for_a_living_or_unknown_animal_passes(status):
    with patch.object(utils, "_recorded_animal_value", AsyncMock(return_value=status)):
        run(utils.validate_animal_not_deceased({"ear_tag_id": "ET0000000013"}, "health event"))


def test_vaccination_health_event_and_breeding_check_it_after_the_ear_tag():
    services = ROOT / "livestock-extension" / "src" / "openg2p_registry_livestock_extension" / "register_domain" / "services"
    for name, kind in [("vaccination", "vaccination"), ("health_event", "health event"), ("breeding", "breeding event")]:
        source = (services / f"g2p_register_domain_service_{name}.py").read_text(encoding="utf-8")
        tag_check = source.index("await self._validate_ear_tag_exists(record, batch_reference)")
        assert source.index(f'await validate_animal_not_deceased(record, "{kind}")') > tag_check


# The resolution date of a disease or an injury is optional, as in the old system.

health = importlib.import_module(SERVICES + "g2p_register_domain_service_health_event")
dates_rule = health.G2PRegisterDomainServiceHealthEvent._validate_event_dates_required


@pytest.mark.parametrize("event_type", ["DISEASE", "INJURY", "TREATMENT"])
def test_a_disease_injury_or_treatment_saves_without_a_resolution_date(event_type):
    dates_rule(None, {"event_type": event_type, "date_onset": "2026-10-01"})


def test_a_recovery_needs_its_resolution_date_and_the_others_their_onset():
    with pytest.raises(G2PRegistryException, match="date of resolution"):
        dates_rule(None, {"event_type": "RECOVERY"})
    with pytest.raises(G2PRegistryException, match="date of onset"):
        dates_rule(None, {"event_type": "DISEASE", "date_resolution": "2026-10-05"})


def test_the_dialog_asks_for_the_resolution_date_only_for_a_recovery():
    sync = META / "patch_ls_health_event_details_sync_ui_schema.sql"
    literal = re.search(r"'(\{\"panels\".*\})'", sync.read_text(encoding="utf-8"), re.S).group(1).replace("''", "'")
    found = {}

    def walk(node):
        if isinstance(node, dict):
            if node.get("column-key") == "date_resolution":
                found.update(node)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(json.loads(literal))
    assert actions(found) == {"show": {"field": "event_type", "value": "TREATMENT", "operator": "notEquals"},
                              "require": {"field": "event_type", "value": "RECOVERY", "operator": "equals"}}
