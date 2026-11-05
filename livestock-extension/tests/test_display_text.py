"""Display text overlay: sentence case labels, DD/MM/YYYY messages, key-based intake tab."""

import json
import re
from pathlib import Path

META = Path(__file__).resolve().parents[1] / "src" / "openg2p_registry_livestock_extension" / "meta_data"
SQL = (META / "zz-oan" / "90_display_text.sql").read_text(encoding="utf-8")
KEY = re.compile(r"^[a-z][a-z0-9_]*$")  # G2PRegisterUITab.validate_tab_label


def translations():
    return json.loads(re.search(r"\|\|\n'(\{.*?\})'::jsonb", SQL, re.DOTALL).group(1))


def test_date_messages_use_the_form_date_format():
    messages = {k: v for k, v in translations().items() if k.startswith("coss_") and "_min" in k}
    assert len(messages) >= 13
    for key, text in messages.items():
        assert "1900-01-01" not in text and text.endswith("on or after 01/01/1900."), key
    assert translations()["coss_input_retag_date_min"].startswith("Date of retagging:")


def test_fayda_and_veterinarian_messages_name_the_labelled_field():
    shown = translations()
    assert shown["coss_input_fayda_fan_id"].startswith("Fayda FAN:")
    assert "Fayda ID (FAN)" not in shown["coss_input_fayda_fan_id"]
    assert shown["coss_input_veterinarian_name"].startswith("Veterinarian:")


def test_animal_table_labels_are_sentence_case():
    for old, new in [("Livestock Ear Tag", "Ear tag"), ("Quantity (Head Count)", "Number of animals (head count)"),
                     ("Secondary Identifier", "Secondary identifier"), ("Add Livestock Details", "Add livestock details"),
                     ("Mixed / Not Applicable", "Mixed or not applicable"), ("Related model", "Record type"),
                     ("Farmer reference", "Farmer link status")]:
        assert old in SQL and new in SQL, old


def test_register_descriptions_and_subject_are_sentence_case():
    descriptions = re.findall(r"\"register_description\" = '([^']+)'", SQL)
    assert len(descriptions) == 10
    for text in descriptions:
        assert text == text[0] + text[1:].lower() or text.startswith("Animals in"), text
    assert "\"register_subject\" = 'Livestock records'" in SQL


def test_intake_tab_is_a_translated_key():
    key = re.search(r'SET "tab_label" = \'([^\']+)\'', SQL).group(1)
    assert KEY.match(key)
    assert translations()[key] == "Livestock intake"
    assert translations()["livestock_livestock_tab"] == "Livestock record"


def test_list_headers_and_status_codes_are_translated():
    shown = translations()
    for key, text in {"ear_tag_id": "Ear tag", "farmer_name": "Farmer name", "total_animals": "Total livestock",
                      "fayda_fan_id": "Fayda FAN ID", "FINAL": "Submitted", "ADD": "New"}.items():
        assert shown[key] == text


def test_statements_are_upgrade_safe():
    assert "DELETE" not in SQL and "NOT IN" not in SQL
