"""The receiving connector's notification schema takes the farmer change notice as the Farmer
registry sends it: a Farmer ID with the FAN or, for a FIN-only farmer, the FIN."""

import json
from pathlib import Path

import pytest

jsonschema = pytest.importorskip("jsonschema")

SCHEMA = json.loads((Path(__file__).resolve().parents[2] / "integrations/farmer-reference/notification.schema.json")
                    .read_text(encoding="utf-8"))


def notice(**fields):
    return {"event_id": "4d2c:2026-10-29T10:19:00", "event_type": "farmer_reference.changed.v1",
            "farmer_id": "FR-297590870792", **fields}


@pytest.mark.parametrize("message", [
    notice(fayda_fin="123456789012"),
    notice(fayda_fan_id="1234567890123456"),
    notice(fayda_fin="123456789012", event_type="farmer-registry.farmer.changed.v1"),
])
def test_accepted(message):
    jsonschema.validate(message, SCHEMA)


@pytest.mark.parametrize("message", [
    notice(),  # no Fayda ID at all
    notice(fayda_fin="1234567890123456"),  # a FAN under the FIN name
    notice(fayda_fan_id="123456789012"),  # a FIN under the FAN name
    notice(fayda_fin="123456789012", event_type="farmer.changed"),
    notice(fayda_fin="123456789012", first_name="Abebe"),  # demographics never travel in the notice
])
def test_rejected(message):
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(message, SCHEMA)
