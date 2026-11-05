"""The geo-hierarchy widget's document fills the per-level Master Data ids."""
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

_spec = importlib.util.spec_from_file_location(
    "geo_hierarchy", Path(__file__).parents[1] / "src" / "openg2p_registry_livestock_extension"
    / "register_domain" / "services" / "geo_hierarchy.py")
geo = sys.modules["geo_hierarchy"] = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(geo)

DOCUMENT = {
    "hierarchy": [
        {"level_id": "l0", "level_mnemonic": "country", "level_value_id": "ET", "level_value_mnemonic": "Ethiopia"},
        {"level_id": "l1", "level_mnemonic": "region", "level_value_id": "ET04", "level_value_mnemonic": "Oromia"},
        {"level_id": "l2", "level_mnemonic": "zone", "level_value_id": "ET0404", "level_value_mnemonic": "East Shewa"},
        {"level_id": "l3", "level_mnemonic": "woreda", "level_value_id": "ET040404", "level_value_mnemonic": "Ada'a"},
        {"level_id": "l4", "level_mnemonic": "kebele", "level_value_id": "ET04040404", "level_value_mnemonic": "Qanani"},
    ],
    "lowest_level_value_id": "ET04040404",
}


def row(**kwargs):
    base = {level: None for level in geo.LEVELS}
    base.update({f"{level}_id": None for level in geo.LEVELS})
    base["geo_code_hierarchy_json"] = None
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_places_use_bare_pcodes_and_skip_the_country():
    assert geo.hierarchy_places(DOCUMENT) == {
        "region": ("ET04", "Oromia"), "zone": ("ET0404", "East Shewa"),
        "woreda": ("ET040404", "Ada'a"), "kebele": ("ET04040404", "Qanani")}


def test_document_may_be_json_text_or_bare_list():
    assert geo.hierarchy_places(json.dumps(DOCUMENT))["woreda"] == ("ET040404", "Ada'a")
    assert geo.hierarchy_places(DOCUMENT["hierarchy"])["kebele"][0] == "ET04040404"
    assert geo.hierarchy_places("not json") == {} and geo.hierarchy_places(None) == {}
    assert geo.hierarchy_places({"hierarchy": [{"level_mnemonic": "region"}]}) == {}


def test_apply_sets_ids_and_missing_names():
    r = row(geo_code_hierarchy_json=DOCUMENT, region="Oromiya")
    assert geo.apply_hierarchy(r) is True
    assert (r.region_id, r.zone_id, r.woreda_id, r.kebele_id) == ("ET04", "ET0404", "ET040404", "ET04040404")
    assert r.region == "Oromiya"  # a given name is kept for Master Data to refresh
    assert (r.zone, r.woreda, r.kebele) == ("East Shewa", "Ada'a", "Qanani")


def test_apply_clears_levels_below_the_chosen_one():
    shorter = {"hierarchy": DOCUMENT["hierarchy"][:4]}
    r = row(geo_code_hierarchy_json=shorter, kebele_id="ET04040404", kebele="Qanani")
    assert geo.apply_hierarchy(r) is True
    assert r.woreda_id == "ET040404" and r.kebele_id is None


def test_apply_without_document_changes_nothing():
    r = row(woreda_id="ET040404")
    assert geo.apply_hierarchy(r) is False
    assert r.woreda_id == "ET040404"
    assert geo.apply_hierarchy(row(geo_code_hierarchy_json="")) is False
