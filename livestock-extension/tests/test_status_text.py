"""Display text for status codes, task context values and tab label keys."""

import json
import re
from pathlib import Path

META = Path(__file__).resolve().parents[1] / "src" / "openg2p_registry_livestock_extension" / "meta_data"
OAN = META / "zz-oan"
JSON_BLOCK = re.compile(r"'(\{.*?\})'::jsonb", re.DOTALL)


def english():
    """The English domain translations after the zz-oan files are applied in file order."""
    merged = {}
    for path in sorted(OAN.glob("*.sql")):
        for block in JSON_BLOCK.findall(path.read_text(encoding="utf-8")):
            try:
                merged.update(json.loads(block))
            except ValueError:
                continue
    return merged


def seeded_text():
    return (META / "registry-configurations" / "registry_languages.sql").read_text(encoding="utf-8")


def test_status_codes_have_display_text():
    texts = english()
    for key, text in {"ADD": "New", "APPROVED": "Approved", "REJECTED": "Rejected", "in_review": "In review",
                      "request_created": "Request created", "completed": "Completed", "skipped": "Skipped"}.items():
        assert texts[key] == text, key


def test_task_context_values_have_display_text():
    texts = english()
    assert texts["registry.change_request.livestock.default"] == "Livestock change"
    assert texts["registry.change_request.livestock-farmer.default"] == "Farmer reference change"
    assert texts["registry.change_request.livestock-farmer.verified-update-skips-review"] == "Farmer reference change (verified)"
    assert texts["registry.intake_form.livestock.default"] == "Livestock intake"
    assert texts["registry.change_request"] == "Change request" and texts["registry.intake_form"] == "Intake form"
    assert texts["ls_farmer_identity"] == "Farmer identity" and texts["UPDATE"] == "Update"


def test_every_register_mnemonic_has_display_text():
    definitions = (META / "register-metadata" / "g2p_register_definitions.sql").read_text(encoding="utf-8")
    texts = english()
    for mnemonic in ("Animal", "Livestock", "Farmer", "VitalEvent", "Breeding", "Vaccination", "Retagging",
                     "VaccineSchedule", "AuditLog", "HealthEvent"):
        assert f"'{mnemonic}'" in definitions, mnemonic
        assert mnemonic in texts or f'"{mnemonic}"' in seeded_text(), mnemonic


def test_the_seed_is_a_named_key_merge_that_replays():
    sql = (OAN / "91_status_text.sql").read_text(encoding="utf-8")
    assert "COALESCE(\"domain_translation\"::jsonb, '{}'::jsonb) ||" in sql
    assert "WHERE \"language_code\" = 'en'" in sql
    assert "DELETE" not in sql.upper()


def test_every_tab_label_key_in_the_seeds_has_an_english_entry():
    tabs = re.findall(r"\('[^']+','[^']+','([^']+)'", (META / "register-metadata" / "g2p_register_ui_tabs.sql").read_text(encoding="utf-8"))
    tabs += re.findall(r"\('[^']+','[^']+','([^']+)'", (META / "register-metadata" / "g2p_intake_form_ui_tabs.sql").read_text(encoding="utf-8"))
    tabs += re.findall(r'"tab_label" = \'([^\']+)\'', "".join(p.read_text(encoding="utf-8") for p in OAN.glob("*.sql")))
    assert {"livestock_farmer_tab", "livestock_livestock_tab", "livestock_animal_tab", "livestock_health_event_tab",
            "livestock_vital_event_tab", "livestock_import_batch_tab"} <= set(tabs)
    texts = english()
    missing = [key for key in set(tabs) if not texts.get(key) and f'"{key}"' not in seeded_text()]
    assert not missing, missing
