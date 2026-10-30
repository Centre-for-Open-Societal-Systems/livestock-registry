"""An approved intake reaching the register makes its holding VERIFIED."""

import importlib
import os
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import pytest

pytest.importorskip("openg2p_registry_core")

PACKAGE = os.environ.get("REGISTRY_EXTENSION_MODULE", "openg2p_registry_livestock_extension")
livestock = importlib.import_module(PACKAGE + ".register_domain.services.g2p_register_domain_service_livestock")
enums = importlib.import_module(PACKAGE + ".register_domain.models.enums")


@pytest.fixture(autouse=True)
def extension_models():
    # The running app reaches the models through the platform alias; a test
    # run on its own has no alias, so hand the service the enum directly.
    with patch.object(livestock, "_extension_models", return_value=SimpleNamespace(LivestockStateEnum=enums.LivestockStateEnum)):
        yield


def holding(state):
    return SimpleNamespace(state=state, state_date=None)


def test_an_ingested_holding_becomes_verified_today():
    for state in (None, "", "DRAFT", "WOREDA_APPROVED"):
        row = holding(state)
        assert livestock.mark_verified(row)
        assert row.state == "VERIFIED"
        assert isinstance(row.state_date, date)


def test_verified_and_archived_holdings_are_left_alone():
    for state in ("VERIFIED", "ARCHIVED"):
        row = holding(state)
        assert not livestock.mark_verified(row)
        assert row.state == state and row.state_date is None
