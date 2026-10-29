"""A record that carries only the chosen place gets its four levels from Master Data."""

import asyncio
import importlib
from types import SimpleNamespace

import pytest

PACKAGE = "openg2p_registry_livestock_extension"
lists = importlib.import_module(f"{PACKAGE}.master_data_lists")
sync = importlib.import_module(f"{PACKAGE}.register_domain.services.admin_area_sync")

INDEX = {
    "ET": {
        "level_value_id": "ET",
        "level_mnemonic": "country",
        "level_value_mnemonic": "Ethiopia",
        "parent_level_value_id": None,
    },
    "ET04": {
        "level_value_id": "ET04",
        "level_mnemonic": "region",
        "level_value_mnemonic": "Oromia",
        "parent_level_value_id": "ET",
    },
    "ET0401": {
        "level_value_id": "ET0401",
        "level_mnemonic": "zone",
        "level_value_mnemonic": "East Shewa",
        "parent_level_value_id": "ET04",
    },
    "ET040101": {
        "level_value_id": "ET040101",
        "level_mnemonic": "woreda",
        "level_value_mnemonic": "Adama",
        "parent_level_value_id": "ET0401",
    },
    "ET04010101": {
        "level_value_id": "ET04010101",
        "level_mnemonic": "kebele",
        "level_value_mnemonic": "Dire Arerti",
        "parent_level_value_id": "ET040101",
    },
}


class FakeClient:
    def __init__(self, index):
        self.index = index

    async def _load_geo_index(self):
        return self.index


def make_row(**kwargs):
    base = {
        name: None
        for name in (
            "region",
            "zone",
            "woreda",
            "kebele",
            "region_id",
            "zone_id",
            "woreda_id",
            "kebele_id",
            "geo_lowest_level_value_id",
            "geo_code_hierarchy_json",
        )
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


@pytest.fixture(autouse=True)
def master_data(monkeypatch):
    monkeypatch.setattr(lists, "_client", lambda: FakeClient(INDEX))
    lists._geo_label_cache.clear()


def run(coro):
    return asyncio.run(coro)


def test_lowest_value_alone_fills_all_four_levels():
    row = make_row(geo_lowest_level_value_id="ET04010101")
    assert run(sync.sync_admin_area(row)) is True
    assert (row.region, row.zone, row.woreda, row.kebele) == (
        "Oromia",
        "East Shewa",
        "Adama",
        "Dire Arerti",
    )
    assert (row.region_id, row.zone_id, row.woreda_id, row.kebele_id) == (
        "ET04",
        "ET0401",
        "ET040101",
        "ET04010101",
    )
    assert row.geo_code_hierarchy_json["lowest_level_value_id"] == "ET04010101"


def test_a_woreda_code_leaves_the_kebele_empty():
    row = make_row(geo_lowest_level_value_id="ET040101")
    run(sync.sync_admin_area(row))
    assert (row.woreda, row.kebele, row.kebele_id) == ("Adama", None, None)


def test_names_pointing_at_their_parent_by_name_still_resolve():
    named = {key: dict(node) for key, node in INDEX.items()}
    named["ET0401"]["parent_level_value_id"] = "Oromia"
    named["ET040101"]["parent_level_value_id"] = "East Shewa"
    named["ET04010101"]["parent_level_value_id"] = "Adama"
    lists._client = lambda: FakeClient(named)
    row = make_row(geo_lowest_level_value_id="ET04010101")
    run(sync.sync_admin_area(row))
    assert (row.region, row.kebele) == ("Oromia", "Dire Arerti")


def test_unknown_code_changes_nothing():
    row = make_row(geo_lowest_level_value_id="ET99999999")
    assert run(sync.sync_admin_area(row)) is False
    assert (row.region, row.zone, row.woreda, row.kebele) == (None, None, None, None)
    assert row.geo_code_hierarchy_json is None


def test_master_data_failure_changes_nothing():
    class Broken:
        async def _load_geo_index(self):
            raise RuntimeError("down")

    lists._client = lambda: Broken()
    row = make_row(geo_lowest_level_value_id="ET04010101")
    assert run(sync.sync_admin_area(row)) is False
    assert row.region is None


def test_an_existing_document_is_left_alone():
    document = {
        "hierarchy": [
            {
                "level_mnemonic": "region",
                "level_value_id": "ET04",
                "level_value_mnemonic": "Oromia",
            }
        ]
    }
    row = make_row(
        geo_lowest_level_value_id="ET04010101", geo_code_hierarchy_json=document
    )
    run(sync.sync_admin_area(row))
    assert row.geo_code_hierarchy_json is document
    assert row.zone_id is None
