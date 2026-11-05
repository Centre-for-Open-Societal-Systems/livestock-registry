"""The extension against the published connector: hook, signature, WebSub content."""

import base64
import json
import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from jwt.api_jws import PyJWS

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from openg2p_registry_connector_extension import registry_signature, startup  # noqa: E402

startup.register()  # what the .pth line does at interpreter start
from openg2p_connector_service.services.ingestion_service import IngestionService  # noqa: E402

KEY = Ed25519PrivateKey.generate()
PEM = KEY.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                        serialization.NoEncryption()).decode()
PUB = KEY.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)


STORED = {"registry_signature": {"key_pem": PEM, "key_id": "livestock-lookup-ed25519-test", "algorithm": "EdDSA"}}


class Connector:
    def __init__(self, transport="websub", secrets=None, **cfg):
        self.transport_type, self._cfg, self._secrets = transport, cfg, secrets
        self.g2p_sender_id, self.g2p_register_mnemonic = "Live_stock_partner_internal", "Farmer"

    def get_source_config(self):
        return self._cfg

    def get_auth_secrets(self):
        return self._secrets or {}


@pytest.fixture
def signing_env(monkeypatch):
    monkeypatch.setenv("CONNECTOR_REGISTRY_SIGNATURE_KEY_PEM", PEM)
    monkeypatch.setenv("CONNECTOR_REGISTRY_SIGNATURE_KEY_ID", "livestock-lookup-ed25519-test")


def svc():
    return IngestionService.__new__(IngestionService)


def crop_d0cd4f9_signature(payload):
    """The crop connector build's scheme (cropsown-regsitry d0cd4f9), proven on New Dev."""
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    protected, _, signature = PyJWS().encode(body, PEM, algorithm="EdDSA",
                                             headers={"kid": "livestock-lookup-ed25519-test"}).split(".")
    return protected + ".." + signature


def test_hook_wraps_the_published_ingestion_service():
    assert getattr(IngestionService._wrap_in_g2p_envelope, "_openg2p_registry_connector_extension", False)
    assert getattr(IngestionService._extract_envelope, "_openg2p_registry_connector_extension", False)


def test_signature_equals_the_scheme_the_registry_verifies_today():
    data = {"event_type": "farmer_reference.changed.v1", "farmer_id": "FR-245216494759",
            "fayda_fan_id": "9988998899889988"}
    env = svc()._wrap_in_g2p_envelope(Connector(secrets=STORED, sign_registry_payload=True), data, "evt-1")
    assert env["header"]["signature_algorithm"] == "EdDSA"
    assert env["header"]["signature"] == crop_d0cd4f9_signature(env["message"]["payload"])
    protected, empty, sig = env["header"]["signature"].split(".")
    assert empty == ""
    body = json.dumps(env["message"]["payload"], sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    compact = ".".join([protected, base64.urlsafe_b64encode(body).rstrip(b"=").decode(), sig])
    assert PyJWS().decode(compact, PUB, algorithms=["EdDSA"]) == body
    assert PyJWS().get_unverified_header(compact)["kid"] == "livestock-lookup-ed25519-test"


def test_unsigned_connector_keeps_the_published_envelope():
    env = svc()._wrap_in_g2p_envelope(Connector("odk_central"), {"a": 1}, "evt-2")
    assert env["header"]["signature"] == "stub-sig" and env["header"]["signature_algorithm"] == "none"


def test_key_from_environment_when_the_connector_holds_none(signing_env):
    env = svc()._wrap_in_g2p_envelope(Connector(sign_registry_payload=True), {"a": 1}, "evt-4")
    assert env["header"]["signature"] == crop_d0cd4f9_signature(env["message"]["payload"])


def test_stored_key_wins_over_environment(monkeypatch):
    monkeypatch.setenv("CONNECTOR_REGISTRY_SIGNATURE_KEY_PEM", "not a key")
    monkeypatch.setenv("CONNECTOR_REGISTRY_SIGNATURE_KEY_ID", "other")
    env = svc()._wrap_in_g2p_envelope(Connector(secrets=STORED, sign_registry_payload=True), {"a": 1}, "evt-5")
    assert env["header"]["signature"] == crop_d0cd4f9_signature(env["message"]["payload"])


def test_odk_credentials_sit_beside_the_signing_key():
    secrets = {"email": "odk@example.org", "password": "x", **STORED}
    connector = Connector("odk_central", secrets=secrets, sign_registry_payload=True)
    env = svc()._wrap_in_g2p_envelope(connector, {"a": 1}, "evt-6")
    assert env["header"]["signature_algorithm"] == "EdDSA"


@pytest.fixture
def helm_env(monkeypatch):
    """What the connector chart renders into the api, worker and beat containers."""
    for name in ("CONNECTOR_REGISTRY_SIGNATURE_KEY_PEM", "CONNECTOR_REGISTRY_SIGNATURE_KEY_ID"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("CONNECTOR_SIGNING_KEY_PEM", PEM)
    monkeypatch.setenv("CONNECTOR_SIGNING_KID", "livestock-lookup-ed25519-test")


def test_key_from_the_helm_signing_variables_when_nothing_else_is_set(helm_env, caplog):
    registry_signature._logged_sources.clear()
    with caplog.at_level("INFO", logger="connector.extension.registry_signature"):
        for i in range(2):
            env = svc()._wrap_in_g2p_envelope(Connector(sign_registry_payload=True), {"a": 1}, f"evt-h{i}")
    assert env["header"]["signature_algorithm"] == "EdDSA"
    assert env["header"]["signature"] == crop_d0cd4f9_signature(env["message"]["payload"])
    lines = [r.getMessage() for r in caplog.records if "key source" in r.getMessage()]
    assert len(lines) == 1 and "CONNECTOR_SIGNING_KEY_PEM" in lines[0]  # once, naming the source
    assert "BEGIN" not in caplog.text and PEM.splitlines()[1] not in caplog.text  # never the key


def test_helm_key_with_escaped_newlines_still_signs(helm_env, monkeypatch):
    monkeypatch.setenv("CONNECTOR_SIGNING_KEY_PEM", PEM.strip().replace("\n", chr(92) + "n"))
    env = svc()._wrap_in_g2p_envelope(Connector(sign_registry_payload=True), {"a": 1}, "evt-h3")
    assert env["header"]["signature"] == crop_d0cd4f9_signature(env["message"]["payload"])


def test_stored_key_wins_over_the_helm_variables(helm_env, monkeypatch, caplog):
    monkeypatch.setenv("CONNECTOR_SIGNING_KEY_PEM", "not a key")
    registry_signature._logged_sources.clear()
    with caplog.at_level("INFO", logger="connector.extension.registry_signature"):
        env = svc()._wrap_in_g2p_envelope(Connector(secrets=STORED, sign_registry_payload=True), {"a": 1}, "evt-h4")
    assert env["header"]["signature"] == crop_d0cd4f9_signature(env["message"]["payload"])
    assert "auth_secret_json.registry_signature" in caplog.text


def test_helm_key_without_kid_fails_closed(helm_env, monkeypatch):
    monkeypatch.delenv("CONNECTOR_SIGNING_KID")
    with pytest.raises(ValueError, match="no key id"):
        svc()._wrap_in_g2p_envelope(Connector(sign_registry_payload=True), {"a": 1}, "evt-h5")


def test_signing_without_key_fails_closed(monkeypatch):
    for name in ("CONNECTOR_SIGNING_KEY_PEM", "CONNECTOR_SIGNING_KID", "CONNECTOR_REGISTRY_SIGNATURE_KEY_PEM",
                 "CONNECTOR_REGISTRY_SIGNATURE_KEY_ID"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ValueError, match="not configured"):
        svc()._wrap_in_g2p_envelope(Connector(sign_registry_payload=True), {"a": 1}, "evt-3")


def test_prewrapped_payload_is_refused_by_a_signing_connector():
    with pytest.raises(ValueError, match="Prewrapped"):
        connector = Connector(secrets=STORED, sign_registry_payload=True)
        svc()._wrap_in_g2p_envelope(connector, {"header": {"sender_id": "x"}}, None)


def test_websub_content_string_is_read_before_data_path():
    notice = {"event_type": "farmer_reference.changed.v1", "farmer_id": "FR-245216494759"}
    raw = {"hub.topic": "oan.farmer-reference.changed.v1", "hub.content": json.dumps(notice)}
    assert svc()._extract_envelope(Connector(websub_content_envelope=True), raw) == notice
    with_path = Connector(websub_content_envelope=True, data_path="farmer_id")
    assert svc()._extract_envelope(with_path, raw) == notice  # non-dict result falls back
    assert svc()._extract_envelope(Connector(), raw) == raw  # switch off: published behaviour


def test_websub_content_that_is_not_an_object_is_refused():
    with pytest.raises(ValueError, match="JSON object"):
        svc()._extract_envelope(Connector(websub_content_envelope=True), {"hub.content": "[1]"})


def test_install_is_idempotent():
    from openg2p_registry_connector_extension.install import install
    before = IngestionService._wrap_in_g2p_envelope
    install(IngestionService)
    assert IngestionService._wrap_in_g2p_envelope is before
