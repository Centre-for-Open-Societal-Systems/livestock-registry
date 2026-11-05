"""Record names show codes as words and identifiers exactly as stored.

plain_code_text treats any all-capitals text as a code, so an ear tag such as
ET0000000123 would become "Et0000000123" if it went through it.
"""

import importlib.util
from pathlib import Path

import pytest

SERVICES = (Path(__file__).resolve().parents[1] / "src" / "openg2p_registry_livestock_extension"
            / "register_domain" / "services")


def _plain_text():
    spec = importlib.util.spec_from_file_location("plain_text", SERVICES / "plain_text.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("key,value", [
    ("ear_tag_id", "ET0000000123"),
    ("ear_tag_id", "FLOCK-2026-01"),
    ("batch_reference", "BATCH_2026_01"),
    ("source_system", "DOVAR"),
    ("vaccine_name", "BCG"),
])
def test_identifiers_and_names_are_kept(key, value):
    assert _plain_text().name_part(key, f" {value} ") == value


@pytest.mark.parametrize("key,value,words", [
    ("event_type", "BIRTH", "Birth"),
    ("vaccine_type", "VACCINE_TYPE_BLACKLEG", "Blackleg"),
    ("species", "CATTLE", "Cattle"),
    ("action_type", "CREATE", "Create"),
])
def test_codes_read_as_words(key, value, words):
    assert _plain_text().name_part(key, value) == words


@pytest.mark.parametrize("module,cls,payload,expected", [
    ("vaccination", "G2PRegisterDomainServiceVaccination",
     {"vaccine_type": "VACCINE_TYPE_BLACKLEG", "ear_tag_id": "ET0000000123"}, "Blackleg ET0000000123"),
    ("vital_event", "G2PRegisterDomainServiceVitalEvent",
     {"event_type": "BIRTH", "ear_tag_id": "ET0000000123"}, "Birth ET0000000123"),
    ("breeding", "G2PRegisterDomainServiceBreeding",
     {"event_type": "NATURAL", "ear_tag_id": "FLOCK-2026-01"}, "Natural FLOCK-2026-01"),
    ("health_event", "G2PRegisterDomainServiceHealthEvent",
     {"event_type": "DISEASE", "ear_tag_id": "ET0000000123"}, "Disease ET0000000123"),
])
def test_service_record_names_keep_the_ear_tag(module, cls, payload, expected):
    pytest.importorskip("openg2p_registry_core")
    service = importlib.import_module(
        f"openg2p_registry_livestock_extension.register_domain.services.g2p_register_domain_service_{module}")
    assert getattr(service, cls).construct_record_name(None, payload) == expected
