"""Species, species settings, breed/vaccine species and default vaccine
intervals come from Master Data (the country pack), not from the registry."""

import asyncio

import pytest

pytest.importorskip("openg2p_registry_core")

from openg2p_registry_livestock_extension import master_data_lists
from openg2p_registry_livestock_extension.register_domain.services import (
    domain_validation_utils as utils,
)

LISTS = {
    "LIVESTOCK_SPECIES": {
        "CATTLE": {"attributes": {"requires_ear_tag": True, "is_flock_species": False}},
        "POULTRY": {"attributes": {"requires_ear_tag": False, "is_flock_species": True}},
        "OTHER": {"attributes": {}},
    },
    "VACCINE_TYPE": {
        "VACCINE_TYPE_NEWCASTLE": {"attributes": {"species": "POULTRY", "interval_days": 90}},
    },
}


@pytest.fixture
def master_data(monkeypatch):
    async def get_list(list_code):
        return LISTS.get(list_code)

    async def parent(value_id):
        return None

    async def display(value_id):
        return {"CATTLE": "Cattle", "POULTRY": "Poultry", "VACCINE_TYPE_NEWCASTLE": "Newcastle"}.get(value_id, value_id)

    monkeypatch.setattr(master_data_lists, "get_list", get_list)
    monkeypatch.setattr(master_data_lists, "parent", parent)
    monkeypatch.setattr(master_data_lists, "display", display)


def run(coro):
    return asyncio.run(coro)


def test_species_settings_are_the_species_attributes(master_data):
    assert run(utils.get_species_config("POULTRY")) == (False, True)
    assert run(utils.get_species_config("CATTLE")) == (True, False)


def test_species_without_settings_needs_an_ear_tag(master_data):
    assert run(utils.get_species_config("OTHER")) == (True, False)
    assert run(utils.get_species_config(None)) == (True, False)


def test_pack_species_is_accepted_and_old_registry_code_is_not(master_data):
    run(utils.validate_species_known({"species": "CATTLE"}))
    with pytest.raises(Exception, match="not in the species list"):
        run(utils.validate_species_known({"species": "LIVESTOCK_SPECIES_CATTLE"}))


def test_unreadable_species_list_does_not_block_a_save(monkeypatch):
    async def get_list(list_code):
        return None

    monkeypatch.setattr(master_data_lists, "get_list", get_list)
    run(utils.validate_species_known({"species": "ANYTHING"}))


def test_vaccine_species_comes_from_its_attribute(master_data):
    run(utils.validate_belongs_to_species("VACCINE_TYPE_NEWCASTLE", "POULTRY", "Vaccine", "VACCINE_TYPE"))
    with pytest.raises(Exception, match="belongs to species 'Poultry', not 'Cattle'"):
        run(utils.validate_belongs_to_species("VACCINE_TYPE_NEWCASTLE", "CATTLE", "Vaccine", "VACCINE_TYPE"))


def test_value_attributes_reads_one_value(master_data):
    assert run(master_data_lists.value_attributes("VACCINE_TYPE", "VACCINE_TYPE_NEWCASTLE"))["interval_days"] == 90
    assert run(master_data_lists.value_attributes("VACCINE_TYPE", "UNKNOWN")) == {}
