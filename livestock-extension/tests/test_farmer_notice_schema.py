"""The receiving connector's notification schema takes the farmer change notice as the Farmer
registry sends it: a Farmer ID with the FAN or, for a FIN-only farmer, the FIN."""

import json
import re
from pathlib import Path

import pytest

SCHEMA = json.loads((Path(__file__).resolve().parents[2] / "integrations/farmer-reference/notification.schema.json")
                    .read_text(encoding="utf-8"))


def valid(message, schema=SCHEMA):
    """The JSON Schema keywords this schema uses, checked as the connector's validator checks them."""
    if schema.get("type") == "object":
        if not isinstance(message, dict) or not set(schema.get("required", [])) <= set(message):
            return False
        if schema.get("additionalProperties") is False and set(message) - set(schema["properties"]):
            return False
        if "anyOf" in schema and not any(valid(message, branch) for branch in schema["anyOf"]):
            return False
        return all(valid(value, schema["properties"][key]) for key, value in message.items()
                   if key in schema.get("properties", {}))
    if "required" in schema:  # an anyOf branch
        return set(schema["required"]) <= set(message)
    if "enum" in schema:
        return message in schema["enum"]
    if not isinstance(message, str):
        return False
    return (schema.get("minLength", 0) <= len(message) <= schema.get("maxLength", len(message))
            and re.search(schema.get("pattern", ""), message) is not None)


def notice(**fields):
    return {"event_id": "4d2c:2026-10-29T10:19:00", "event_type": "farmer_reference.changed.v1",
            "farmer_id": "FR-297590870792", **fields}


def test_the_schema_only_uses_the_keywords_checked_here():
    assert set(SCHEMA) == {"type", "required", "anyOf", "additionalProperties", "properties"}
    for field in SCHEMA["properties"].values():
        assert set(field) <= {"type", "minLength", "maxLength", "pattern", "enum"}


@pytest.mark.parametrize("message", [
    notice(fayda_fin="123456789012"),
    notice(fayda_fan_id="1234567890123456"),
    notice(fayda_fin="123456789012", event_type="farmer-registry.farmer.changed.v1"),
])
def test_accepted(message):
    assert valid(message)


@pytest.mark.parametrize("message", [
    notice(),  # no Fayda ID at all
    notice(fayda_fin="1234567890123456"),  # a FAN under the FIN name
    notice(fayda_fan_id="123456789012"),  # a FIN under the FAN name
    notice(fayda_fin="123456789012", event_type="farmer.changed"),
    notice(fayda_fin="123456789012", first_name="Abebe"),  # demographics never travel in the notice
])
def test_rejected(message):
    assert not valid(message)
