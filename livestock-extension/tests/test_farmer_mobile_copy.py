"""A farmer's mobile number copied from the Farmer Registry passes Livestock's rule.

The Farmer Registry publishes the national number without its trunk 0
(912148121). Livestock stores mobile numbers as +251 or 0 followed by 9
digits, so the copy is normalized before the rule runs, and a refusal names
the field as the officer sees it.
"""

import importlib

import pytest

p = importlib.import_module("openg2p_registry_livestock_extension.farmer_reference.profile")


@pytest.mark.parametrize("value, stored", [
    ("912148121", "+251912148121"),
    ("712 148 121", "+251712148121"),
    ("251912148121", "+251912148121"),
    ("+251912148121", "+251912148121"),
    ("0912148121", "0912148121"),
    ("", ""),
    (None, None),
])
def test_copied_mobile_number_is_stored_in_livestock_format(value, stored):
    assert p.local_profile({"mobile_number": value}) == {"mobile_number": stored}


def test_unrecognised_mobile_number_is_left_for_the_rule_to_refuse():
    assert p.local_profile({"mobile_number": "12345"}) == {"mobile_number": "12345"}


@pytest.mark.parametrize("module_name, cls", [
    ("g2p_register_domain_service_farmer", "G2PRegisterDomainServiceFarmer"),
    ("g2p_register_domain_service_livestock", "G2PRegisterDomainServiceLivestock"),
])
def test_refusals_name_the_field_in_plain_words(module_name, cls):
    pytest.importorskip("openg2p_registry_core")
    module = importlib.import_module(
        "openg2p_registry_livestock_extension.register_domain.services." + module_name)
    service = object.__new__(getattr(module, cls))
    with pytest.raises(Exception) as refused:
        service._validate_mobile_number({"mobile_number": "912148121"}, "mobile_number")
    assert "Mobile Number: enter an Ethiopian mobile number" in str(refused.value)
    assert "mobile_number" not in str(refused.value)
    with pytest.raises(Exception) as refused:
        service._validate_farmer_id({"farmer_id": "FR-1"})
    assert str(refused.value).count("Farmer ID: enter FR- followed by exactly 12 digits") == 1
    assert "farmer_id" not in str(refused.value)
