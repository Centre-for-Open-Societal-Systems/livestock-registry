"""The record status header lets an approved change request close a record."""

import json
import os
import re
from pathlib import Path

import pytest

PACKAGE = os.environ.get("REGISTRY_EXTENSION_MODULE", "openg2p_registry_livestock_extension")
META = Path(__file__).resolve().parents[1] / "src" / PACKAGE / "meta_data" / "register-metadata"
OVERLAY = META / "record_status_header.sql"


def header_sections():
    text = OVERLAY.read_text(encoding="utf8")
    found = {}
    for match in re.finditer(r"\(\x27([0-9a-f-]{36})\x27,\x27([a-z_]+)\x27,\x27[0-9a-f-]{36}\x27,.*?,\x27(\{\"panels\".*?\})\x27,\x27FALSE\x27", text):
        found[match.group(2)] = (match.group(1), json.loads(match.group(3)))
    return found


def test_each_header_binds_the_record_status_and_reason():
    sections = header_sections()
    assert set(sections) == {"livestock_record_header", "livestock_farmer_record_header"}
    for section_id, (register_id, schema) in sections.items():
        assert schema["section-editable"] is True and schema["section-id"] == section_id
        (widget,) = schema["panels"][0]["panels"][0]["widgets"]
        assert widget["widget"] == "header-section"
        assert widget["widget-data-path"]["status"] == register_id + ".record_status"
        assert widget["widget-data-path"]["statusReason"] == register_id + ".record_status_reason"
        labels = [o["label"] for o in widget["widget-field-config"]["status"]["data-source"]["options"]]
        assert labels == ["Active", "Inactive", "Archived"]


def test_the_platform_accepts_a_status_change_on_the_header():
    core = pytest.importorskip("openg2p_registry_core.services.g2p_change_request_section_payload_service")
    service = core.G2PChangeRequestSectionPayloadService.__new__(core.G2PChangeRequestSectionPayloadService)
    orm_fields = {"record_name", "record_status", "record_status_reason", "functional_record_id", "farmer_id"}
    for register_id, schema in header_sections().values():
        allowed = service.resolve_allowed_fields(schema, register_id, orm_fields)
        assert {"record_status", "record_status_reason"} <= allowed
        assert "farmer_id" not in allowed


def test_the_header_sorts_after_the_base_section_files():
    names = sorted(p.name for p in META.glob("*.sql"))
    assert names.index(OVERLAY.name) > names.index("g2p_register_sections.sql")
    assert names.index(OVERLAY.name) > names.index("g2p_register_ui_tab_sections.sql")
    for path in META.glob("*.sql"):
        if path.name > OVERLAY.name:
            body = path.read_text(encoding="utf8")
            for section_id in header_sections():
                assert section_id not in body, path.name
