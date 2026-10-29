"""Register tab labels are lowercase translation keys with English display text.

The platform validator rejects any other tab_label when a tab is rebuilt from the
metadata cache, which made the change request search fail with SYS-ERR-001.
"""

import json
import re
from pathlib import Path

META = Path(__file__).resolve().parents[1] / "src" / "openg2p_registry_livestock_extension" / "meta_data"
SEED = META / "register-metadata" / "g2p_register_ui_tabs.sql"
OVERLAY = META / "zz-oan" / "50_tab_label_keys.sql"
KEY = re.compile(r"^[a-z][a-z0-9_]*$")  # G2PRegisterUITab.validate_tab_label


def seeded_tabs():
    return dict(re.findall(r"^\('([^']+)','[^']+','([^']+)',", SEED.read_text(encoding="utf-8"), re.M))


def test_seeded_labels_are_keys():
    tabs = seeded_tabs()
    assert tabs
    for tab_id, label in tabs.items():
        assert KEY.match(label), (tab_id, label)


def test_overlay_rekeys_and_translates_every_tab():
    text = OVERLAY.read_text(encoding="utf-8")
    rekeyed = set(re.findall(r"^\s+'([a-z_]+)',?$", text, re.M))
    translations = json.loads(re.search(r"\('(\{.*?\})'::jsonb", text, re.S).group(1))
    for tab_id, label in seeded_tabs().items():
        assert tab_id in rekeyed
        assert translations.get(label), label


def test_platform_validator_accepts_the_labels():
    import pytest

    tab_module = pytest.importorskip("openg2p_registry_core.models.g2p_register_tab")
    for tab_id, label in seeded_tabs().items():
        tab_module.G2PRegisterUITab(tab_id=tab_id, register_id="r", tab_label=label, tab_order=0, is_active=True)
    with pytest.raises(ValueError):
        tab_module.G2PRegisterUITab(tab_id="t", register_id="r", tab_label="Farmer", tab_order=0, is_active=True)
