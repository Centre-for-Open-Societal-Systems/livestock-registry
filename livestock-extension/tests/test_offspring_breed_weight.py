"""A Birth event can record the offspring's breed (a cross) and birth weight;
both are optional and reach the newborns' Animal rows."""

import asyncio
import json
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
EXT = ROOT / "livestock-extension" / "src" / "openg2p_registry_livestock_extension"
METADATA = EXT / "meta_data" / "register-metadata"
BIRTH_ONLY = {"actions": [{"action": "show", "condition": {"field": "event_type", "value": "BIRTH", "operator": "equals"}}]}


def vital_columns(path):
    text = path.read_text(encoding="utf-8")
    for match in re.finditer(r"'(\{.*?\})'(?=::jsonb|\s*[,)])", text, re.S):
        literal = match.group(1).replace("''", "'")
        if '"ls_vital_event_details_table"' not in literal:
            continue
        found = {}

        def walk(node):
            if isinstance(node, dict):
                if node.get("widget-id") == "ls_vital_event_details_table":
                    found.update({c["column-key"]: c for c in node["widget-data-columns"]})
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        walk(json.loads(literal))
        return found
    raise AssertionError(f"no vital event table in {path.name}")


@pytest.mark.parametrize("name", ["g2p_register_sections.sql", "patch_ls_vital_event_details_sync_ui_schema.sql"])
def test_birth_dialog_offers_breed_and_weight_of_the_offspring(name):
    columns = vital_columns(METADATA / name)
    keys = list(columns)
    assert keys.index("offspring_breed") == keys.index("offspring_gender") + 1
    assert keys.index("offspring_weight") == keys.index("offspring_breed") + 1
    breed, weight = columns["offspring_breed"], columns["offspring_weight"]
    assert breed["widget-data-source"]["params"]["attribute_id"] == "LIVESTOCK_BREED"
    assert breed["widget-data-source"]["valueKey"] == "value_id"
    assert weight["widget-data-format"]["numericType"] == "decimal"
    for column in (breed, weight):
        assert column["widget-data-options"] == BIRTH_ONLY
        assert not column.get("widget-required")


def test_model_and_migration_carry_the_columns():
    model = (EXT / "register_domain" / "models" / "vital_event.py").read_text(encoding="utf-8")
    assert "offspring_breed: Mapped[str] = mapped_column(String, nullable=True)" in model
    assert "offspring_weight: Mapped[float] = mapped_column(Float, nullable=True)" in model
    migration = (ROOT / "docker" / "db-seed" / "migrations" / "0012_vital_events_offspring_breed_weight.sql").read_text(encoding="utf-8")
    for table in ("g2p_register_vital_events", "g2p_register_history_vital_events", "g2p_intake_form_vital_events"):
        assert f"ALTER TABLE {table}\n    ADD COLUMN IF NOT EXISTS offspring_breed VARCHAR," in migration


@pytest.fixture
def service(monkeypatch):
    pytest.importorskip("openg2p_registry_core")
    from openg2p_registry_livestock_extension.register_domain.services import (
        g2p_register_domain_service_vital_event as module,
    )

    checked = []

    async def known(record, field, attribute_id, label):
        checked.append(("known", record[field], attribute_id))
        if record[field] == "BREED_UNKNOWN":
            module.validation_error(f"{label} 'BREED_UNKNOWN' is not in the list.")

    async def belongs(value_id, species, kind, list_code=None):
        checked.append(("species", value_id, species))

    monkeypatch.setattr(module, "validate_known_code", known)
    monkeypatch.setattr(module, "validate_belongs_to_species", belongs)
    return module.G2PRegisterDomainServiceVitalEvent.__new__(module.G2PRegisterDomainServiceVitalEvent), checked


def check(service, **record):
    return asyncio.run(service._validate_offspring_breed_and_weight(record))


def test_both_are_optional(service):
    svc, checked = service
    check(svc, event_type="BIRTH", species="CATTLE")
    assert checked == []


def test_a_birth_breed_is_checked_against_the_list_and_the_species(service):
    svc, checked = service
    check(svc, event_type="BIRTH", species="CATTLE", offspring_breed="BREED_HYBRID", offspring_weight="28.5")
    assert checked == [("known", "BREED_HYBRID", "LIVESTOCK_BREED"), ("species", "BREED_HYBRID", "CATTLE")]


@pytest.mark.parametrize("record, message", [
    ({"event_type": "MORTALITY", "offspring_weight": 20}, "only recorded for a birth"),
    ({"event_type": "BIRTH", "offspring_weight": 0}, "greater than zero"),
    ({"event_type": "BIRTH", "offspring_weight": "-3"}, "greater than zero"),
    ({"event_type": "BIRTH", "offspring_breed": "BREED_UNKNOWN"}, "not in the list"),
])
def test_wrong_values_are_refused(service, record, message):
    svc, _ = service
    with pytest.raises(Exception, match=message):
        check(svc, species="CATTLE", **record)
