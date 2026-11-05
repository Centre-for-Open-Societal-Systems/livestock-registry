"""Every refusal tells the submitter what is wrong and how to fix it."""

import importlib
import os
from types import SimpleNamespace

PACKAGE = os.environ.get("REGISTRY_EXTENSION_MODULE", "openg2p_registry_livestock_extension")
messages = importlib.import_module(PACKAGE + ".farmer_reference.messages")


def test_not_found_names_the_ids_and_the_fix():
    text = messages.explain("FARMER_REFERENCE_NOT_FOUND",
                            {"farmer_id": "FR-000000000001", "fayda_fin": "001234567890"})
    assert "No farmer with Farmer ID FR-000000000001 and FIN 001234567890" in text
    assert "register them in the Farmer Registry first" in text


def test_every_message_is_explained_without_a_raw_code():
    for code in messages.MESSAGES:
        text = messages.explain(code, {"farmer_id": "FR-1"})
        assert "FARMER_REFERENCE_" not in text and "{" not in text


def test_unreachable_source_says_nothing_was_submitted():
    for code in messages.UNAVAILABLE:
        assert "Nothing was submitted" in messages.explain(code)


def test_unknown_code_is_never_shown_and_sentences_pass_through():
    assert "FARMER_REFERENCE_SOMETHING_NEW" not in messages.explain("FARMER_REFERENCE_SOMETHING_NEW")
    assert messages.explain("Fayda FIN: enter exactly 12 digits") == "Fayda FIN: enter exactly 12 digits"


def test_held_worker_diagnostic_says_the_intake_was_saved():
    text = messages.explain("FARMER_REFERENCE_LOOKUP_UNAVAILABLE", held=True)
    assert "This intake is saved and held" in text
    assert "Nothing was submitted" not in text


def test_held_texts_match_the_crop_registry():
    assert messages.WAITING_FOR_FARMER_APPROVAL == "Approved, waiting for Farmer approval"
    assert messages.FARMER_REFERENCE_LINKED == "Farmer reference linked"
    assert messages.FARMER_REFERENCE_AWAITING == (
        "Farmer reference awaiting approval; the record will be added after that approval")
    assert messages.FARMER_LOOKUP_PENDING == (
        "Waiting for the Farmer lookup; the record will be added once the farmer is found and approved")
    assert messages.FARMER_APPROVAL_REJECTED == (
        "Approved, but the Farmer registration was rejected, so this record was not added. "
        "Check the Farmer ID and Fayda ID, or ask the approver why, and submit a new intake")
    assert messages.FARMER_REFERENCE_MISSING == (
        "Approved, but no Farmer registration is linked to this intake, so this record was not added. "
        "Ask the administrator to check the intake")


def test_held_text_follows_the_farmer_reference():
    pending = SimpleNamespace(state="PENDING")
    assert messages.held_text(None, pending) == messages.WAITING_FOR_FARMER_APPROVAL
    assert messages.held_text(None, None) == messages.FARMER_REFERENCE_MISSING
    assert messages.held_text(SimpleNamespace(state="PENDING"), None) == messages.WAITING_FOR_FARMER_APPROVAL
    assert messages.held_text(SimpleNamespace(state="REJECTED"), None) == messages.FARMER_APPROVAL_REJECTED


def test_held_texts_are_readable_sentences():
    for text in (messages.WAITING_FOR_FARMER_APPROVAL, messages.FARMER_APPROVAL_REJECTED,
                 messages.FARMER_REFERENCE_MISSING, messages.FARMER_LOOKUP_PENDING,
                 messages.FARMER_REFERENCE_AWAITING, messages.FARMER_REFERENCE_LINKED):
        assert "FARMER_REFERENCE_" not in text and "_" not in text and text == text.strip()


def test_rows_held_with_the_old_code_are_still_recognised_as_waiting():
    assert messages.is_waiting_text("FARMER_REFERENCE_DEPENDENCY_PENDING")
    assert messages.is_waiting_text(messages.WAITING_FOR_FARMER_APPROVAL)
    assert messages.is_waiting_text(messages.FARMER_LOOKUP_PENDING)
    assert not messages.is_waiting_text(messages.FARMER_APPROVAL_REJECTED)
    assert not messages.is_waiting_text(None)
