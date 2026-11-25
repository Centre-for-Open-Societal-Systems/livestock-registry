"""Guard: every consent scope id the repository names is one the partner API can release.

At the pinned platform the partner API clamps a DCI search response to the consent's effective data scopes by
matching them against the TOP-LEVEL keys of the rendered search response (openg2p_registry_partner_api,
G2PDciService._clamp_record_fields): any other scope name matches nothing and releases nothing, without an error.
So a valid scope id is a top-level key of the Livestock register's outgoing DCI template: the document
outgoing_templates.sql binds to the register, which g2p_registry_documents.sql names
templates/openg2p_livestock_to_dci.json.j2.

The scope ids named here are the sanity DCI e2e's consented and denied scopes, helm values
registry.sanity.dataScopes / deniedScopes, which the platform chart passes to the sanity image as
SANITY_DATA_SCOPES / SANITY_DENIED_SCOPES. Livestock ships no data-scopes catalogue of its own.
"""

import json
import re

import yaml
from jinja2 import Environment

from test_metadata_consistency import EXT, ROOT, REGISTER_METADATA, definitions

VALUES = ROOT / "helm/openg2p-livestock-registry/values.yaml"


def outgoing_template():
    """The file name of the Livestock register's outgoing template."""
    livestock = next(i for i, (mnemonic, _) in definitions().items() if mnemonic == "Livestock")
    bindings = (EXT / "meta_data/registry-outbound-messages-templates/outgoing_templates.sql").read_text()
    documents = dict(re.findall(r"\('([0-9a-f-]{36})','([^']+)','templates'",
                                (REGISTER_METADATA / "g2p_registry_documents.sql").read_text()))
    (document,) = re.findall(rf"\('[^']+','[0-9a-f-]+','{livestock}','([0-9a-f-]+)'", bindings)
    return documents[document]


def releasable_scopes():
    template = (EXT / "templates" / outgoing_template()).read_text(encoding="utf-8")
    return set(json.loads(Environment().from_string(template).render()))


def named_scopes():
    """(where, scope id) for every consent scope id the repository names."""
    sanity = yaml.safe_load(VALUES.read_text(encoding="utf-8"))["registry"]["sanity"]
    for key in ("dataScopes", "deniedScopes"):
        for scope in str(sanity.get(key) or "").split(","):
            if scope.strip():
                yield f"values.yaml registry.sanity.{key}", scope.strip()


def test_consent_scope_ids_are_releasable():
    assert outgoing_template() == "openg2p_livestock_to_dci.json.j2"
    releasable = releasable_scopes()
    assert {"livestock_details", "animal_details", "breeding_details"} <= releasable, releasable
    named = set(named_scopes())
    assert ("values.yaml registry.sanity.dataScopes", "livestock_details") in named
    assert ("values.yaml registry.sanity.deniedScopes", "breeding_details") in named
    invalid = sorted((where, scope) for where, scope in named if scope not in releasable)
    assert not invalid, invalid
