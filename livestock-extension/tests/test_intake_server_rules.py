"""Server-side intake rules: the registry's date, plain messages, one validate and submit."""

import asyncio
import importlib
import os
from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

pytest.importorskip("openg2p_registry_core")

PACKAGE = os.environ.get("REGISTRY_EXTENSION_MODULE", "openg2p_registry_livestock_extension")
SERVICES = PACKAGE + ".register_domain.services."
local_date = importlib.import_module(SERVICES + "local_date")
rules = importlib.import_module(SERVICES + "field_rules")
messages = importlib.import_module(SERVICES + "attribute_messages")
utils = importlib.import_module(SERVICES + "domain_validation_utils")
animal = importlib.import_module(SERVICES + "g2p_register_domain_service_animal")
required_fields = importlib.import_module(PACKAGE + ".required_fields")
required_intake = importlib.import_module(PACKAGE + ".required_intake")
master_data_lists = importlib.import_module(PACKAGE + ".master_data_lists")
from openg2p_registry_core.errors import G2PRegistryException


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _no_remembered_farmer_answers():
    native = importlib.import_module(PACKAGE + ".farmer_reference.native")
    native._answers.clear()
    yield
    native._answers.clear()


# A. the registry's date --------------------------------------------------------

def test_a_utc_evening_is_already_the_next_day_in_ethiopia():
    # 22:30 UTC on 29 October is 01:30 on 30 October in Addis Ababa.
    assert local_date.local_today(datetime(2026, 10, 29, 22, 30, tzinfo=UTC)) == date(2026, 10, 30)
    assert local_date.local_today(datetime(2026, 10, 29, 20, 59, tzinfo=UTC)) == date(2026, 10, 29)


def test_without_a_time_zone_database_the_fixed_offset_gives_the_same_date():
    with patch.object(local_date, "_zone", return_value=local_date._FALLBACK):
        assert local_date.local_today(datetime(2026, 10, 29, 22, 30, tzinfo=UTC)) == date(2026, 10, 30)
    with patch("zoneinfo.ZoneInfo", side_effect=KeyError("no tzdata")):
        assert local_date._zone() is local_date._FALLBACK


def test_todays_registry_date_is_accepted_when_the_utc_date_is_still_yesterday():
    with patch.object(rules, "local_today", return_value=date(2026, 10, 30)):
        assert rules.clean_records([{"registration_date": "2026-10-30"}]) == []
        record = {"registration_date": "today"}
        assert rules.clean_records([record]) == []
        assert record["registration_date"] == "2026-10-30"


def test_a_date_after_the_registry_date_is_still_in_the_future():
    with patch.object(rules, "local_today", return_value=date(2026, 10, 30)):
        problems = rules.clean_records([{"date_of_birth": "2026-10-31"}])
    assert [p.key for p in problems] == ["coss_field_date_future"]


@pytest.mark.parametrize(
    "name", ["animal", "vaccination", "health_event", "vital_event", "breeding", "livestock", "retagging"]
)
def test_every_not_in_the_future_check_reads_the_registry_date(name):
    module = importlib.import_module(SERVICES + "g2p_register_domain_service_" + name)
    assert module.local_today is local_date.local_today


# B. plain words for a value that is not on its list ----------------------------

SPECIES = {"CATTLE": "Cattle", "GOATS": "Goats", "SHEEP": "Sheep"}
RAW = "record 0: species='DOG' is not a value of LIVESTOCK_SPECIES (permitted: CATTLE, GOATS, SHEEP)"


def test_an_unknown_species_names_the_field_and_shows_the_labels_in_list_order():
    text = messages.reword(RAW, {"LIVESTOCK_SPECIES": SPECIES})
    assert text == "Species: choose a species from the list (Cattle, Goats, Sheep)."


def test_without_labels_the_codes_are_made_readable_never_shown_raw():
    text = messages.reword(RAW.replace("SHEEP", "UP_TO_DATE"), {})
    assert text == "Species: choose a species from the list (Cattle, Goats, Up to date)."


def test_every_coded_field_gets_its_own_sentence_and_other_text_is_kept():
    raw = (
        "record 0: gender='X' is not a value of GENDER (permitted: FEMALE, MALE); "
        "record 0: breed='Q' is not a value of LIVESTOCK_BREED (permitted: BREED_BORAN); Something else"
    )
    text = messages.reword(raw, {"GENDER": {"MALE": "Male", "FEMALE": "Female"}})
    assert text == (
        "Sex: choose one from the list (Male, Female). Breed: choose a breed from the list (Boran). Something else"
    )


def test_a_long_list_is_cut_short():
    codes = [f"BREED_{n:02d}" for n in range(12)]
    raw = f"record 0: breed='x' is not a value of LIVESTOCK_BREED (permitted: {', '.join(codes)})"
    assert messages.reword(raw, {}).endswith("(00, 01, 02, 03, 04, 05, 06, 07, 08, 09 and 2 more).")


def test_a_message_that_is_not_about_a_list_is_unchanged():
    assert messages.reword("Weight must be greater than zero.", {}) == "Weight must be greater than zero."


def test_the_installed_validator_rewords_what_core_refuses(monkeypatch):
    core = importlib.import_module("openg2p_registry_core.services.g2p_attribute_value_validator")
    monkeypatch.setattr(core.G2PAttributeValueValidator, "enabled", property(lambda self: True))
    monkeypatch.setattr(
        core.G2PAttributeValueValidator, "_load", AsyncMock(return_value={"LIVESTOCK_SPECIES": set(SPECIES)})
    )

    async def values(attribute):
        return [{"value_id": code, "value_display": label} for code, label in SPECIES.items()]

    monkeypatch.setattr(master_data_lists, "get_values", values)
    monkeypatch.setattr(rules, "_translations", AsyncMock(return_value={}))
    validator = messages.install_attribute_messages()
    field_map = {"species": "LIVESTOCK_SPECIES"}
    with pytest.raises(G2PRegistryException) as caught:
        run(validator.validate_records([{"species": "DOG"}], field_map=field_map))
    assert caught.value.message == "Species: choose a species from the list (Cattle, Goats, Sheep)."
    run(validator.validate_records([{"species": "GOATS"}], field_map=field_map))
    assert messages.install_attribute_messages() is validator


# C. required-field message -----------------------------------------------------

def _column(key, label):
    return {"widget": "select", "column-key": key, "widget-label": label, "widget-required": True}


ANIMALS = {
    "section-title": "Livestock Details",
    "panels": [
        {
            "widgets": [
                {
                    "widget": "dialog-table",
                    "widget-id": "animals",
                    "widget-label": "Livestock Details",
                    "widget-data-columns": [_column("species", "Species"), _column("gender", "Sex")],
                }
            ]
        }
    ],
}


def test_the_message_uses_the_column_label_and_joins_the_fields_readably():
    # the registry's translation of the field name says "Gender": the label on the form wins
    translated = {"gender": "Gender", "species": "Species"}
    problems = required_fields.section_problems(ANIMALS, True, [{}], {}, translated)
    assert problems == ["Livestock details, row 1: fill in Species and Sex"]


def test_a_translated_label_key_still_translates_and_a_bare_field_falls_back_to_its_name():
    key_label = {"widget": "text", "widget-label": "ls_animal_sex", "widget-id": "gender"}
    assert required_fields.Words({"ls_animal_sex": "Sex"}).label(key_label, "gender") == "Sex"
    assert required_fields.Words().label(key_label, "gender") == "Ls animal sex"
    assert required_fields.Words({"gender": "Sex"}).label({"widget-id": "gender"}, "gender") == "Sex"


def test_three_fields_read_as_a_list_and_capitals_in_a_section_title_stay():
    assert required_fields.join_words(["A", "B", "C"]) == "A, B and C"
    assert required_fields.join_words(["A"]) == "A"
    assert required_fields.sentence_case("Survey Personnel DA Details") == "Survey personnel DA details"


def test_the_refusal_is_one_sentence_per_item():
    joined = required_fields.join_sentences(
        ["Farmer ID: enter the ID.", "Fayda ID: enter the FAN", "Farmer ID: enter the ID."]
    )
    assert joined == "Farmer ID: enter the ID. Fayda ID: enter the FAN."
    with patch.object(rules, "_translations", AsyncMock(return_value={})):
        with pytest.raises(G2PRegistryException) as caught:
            run(rules.validate_record_fields([{"farmer_id": "", "fayda_id": ""}]))
    assert ".;" not in caught.value.message and "; " not in caught.value.message
    assert caught.value.message.count("Farmer ID") == 1


# D. a tag used twice in the same form --------------------------------------------

ROW = {"ear_tag_id": "ET0000000123", "species": "CATTLE", "breed": "BREED_LOCAL", "application_reference": "APP-1"}


def _check(clash, rows):
    service = object.__new__(animal.G2PRegisterDomainServiceAnimal)
    with patch.object(animal, "ear_tag_clash", AsyncMock(return_value=clash)):
        run(service._validate_no_duplicate_ear_tags(rows))


def test_a_tag_found_in_this_same_form_says_so():
    with pytest.raises(G2PRegistryException) as caught:
        _check(utils.TableMatch("intake", "APP-1"), [ROW])
    assert caught.value.message == "Ear tag ET0000000123 is already used for another animal in this form."


def test_a_tag_found_in_another_unapproved_form_is_not_called_registered():
    with pytest.raises(G2PRegistryException) as caught:
        _check(utils.TableMatch("intake", "APP-2"), [ROW])
    assert caught.value.message == (
        "Ear tag ET0000000123 is already used for an animal in another intake form that is not yet approved."
    )


def test_a_tag_found_in_the_register_keeps_the_register_message():
    with pytest.raises(G2PRegistryException) as caught:
        _check(utils.TableMatch("register"), [ROW])
    assert caught.value.message == (
        "Ear tag ET0000000123 is already registered to a different animal of the same species and breed."
    )


def test_two_rows_with_one_tag_in_the_same_save_say_this_form():
    with pytest.raises(G2PRegistryException) as caught:
        _check(None, [ROW, dict(ROW)])
    assert caught.value.message == "Ear tag ET0000000123 is already used for another animal in this form."


def test_a_tag_nobody_uses_passes():
    _check(None, [ROW])


def test_an_event_for_an_unknown_tag_says_where_it_looked():
    module = importlib.import_module(SERVICES + "g2p_register_domain_service_vaccination")
    service = object.__new__(module.G2PRegisterDomainServiceVaccination)
    with patch.object(module, "ear_tag_exists", AsyncMock(return_value=False)):
        with pytest.raises(G2PRegistryException) as caught:
            run(service._validate_ear_tag_exists({"ear_tag_id": "ET9999999999"}, None))
    assert caught.value.message == (
        "No animal with ear tag ET9999999999 in this form or the register. "
        "Add it under Livestock details first, or check for a typo."
    )


# E. validate says what Submit says ----------------------------------------------

class _Base:
    async def validate_submission_for_approval_with_session(self, submission_id, session):
        return SimpleNamespace(issues=[], is_valid=True)


class _Service(required_intake.RequiredFieldsMixin, _Base):
    def __init__(self, problems):
        self.problems = problems

    async def _required_on_finalize(self, submission_id, session):
        return self.problems


def test_validate_reports_what_submit_would_refuse():
    service = _Service(["Survey personnel: fill in DA name", "Livestock details: add at least one row"])
    result = run(service.validate_submission_for_approval_with_session("s", None))
    assert not result.is_valid
    assert [i.message for i in result.issues] == [
        "Survey personnel: fill in DA name.",
        "Livestock details: add at least one row.",
    ]
    assert {i.code for i in result.issues} == {"SUBMISSION_INCOMPLETE"}


def test_validate_is_valid_for_a_complete_form():
    result = run(_Service([]).validate_submission_for_approval_with_session("s", None))
    assert result.is_valid and result.issues == []


def _reference_service(problem):
    native = importlib.import_module(PACKAGE + ".farmer_reference.native")
    service = object.__new__(native.ReferenceIntakeService)
    service._farmer_problem = AsyncMock(return_value=problem)
    return service


def _validate(service, base):
    with patch.object(
        required_intake.RequiredFieldsMixin, "validate_submission_for_approval_with_session",
        AsyncMock(return_value=base),
    ):
        return run(service.validate_submission_for_approval_with_session("s", None))


def test_validate_reports_a_farmer_who_cannot_be_linked():
    service = _reference_service(("FARMER_NOT_FOUND", "No farmer with Farmer ID FR-000000000001 is in the Farmer Registry"))
    result = _validate(service, SimpleNamespace(issues=[], is_valid=True))
    assert not result.is_valid
    assert result.issues[0].code == "FARMER_NOT_FOUND"
    assert result.issues[0].message == "No farmer with Farmer ID FR-000000000001 is in the Farmer Registry."


def test_the_farmer_is_not_looked_up_while_the_form_is_still_incomplete():
    service = _reference_service("anything")
    result = _validate(service, SimpleNamespace(issues=["missing"], is_valid=False))
    service._farmer_problem.assert_not_called()
    assert result.issues == ["missing"]


class _Rows:
    def __init__(self, rows):
        self.rows = rows

    def scalars(self):
        return self

    def all(self):
        return self.rows


class _Query:
    def where(self, *args):
        return self


class _Dependency:
    pass


class _Live:
    pass


def _farmer_session(row, dependency=None):
    async def get(model, key):
        return dependency if model is _Dependency else None

    return SimpleNamespace(get=get, execute=AsyncMock(return_value=_Rows([row])))


def _lookup_service(monkeypatch, lookup):
    native = importlib.import_module(PACKAGE + ".farmer_reference.native")
    service = object.__new__(native.ReferenceIntakeService)
    service._get_submission_or_error = AsyncMock(return_value=SimpleNamespace(register_id="r"))
    service._get_register_definition = AsyncMock(return_value=SimpleNamespace(register_mnemonic="Livestock"))
    models = SimpleNamespace(G2PIntakeFormLivestock=SimpleNamespace(submission_id=1), G2PRegisterLivestock=_Live)
    monkeypatch.setattr(native, "domain_models", lambda: models)
    monkeypatch.setattr(native, "select", lambda *a: _Query())
    monkeypatch.setattr(native, "FarmerSubmissionDependency", _Dependency)
    monkeypatch.setattr(native, "configured_lookup", lambda: SimpleNamespace(lookup=lookup))
    return service


def _row():
    return SimpleNamespace(
        internal_record_id="x", farmer_id="FR-123456789012", fayda_fin=None, fayda_fan_id="1234567890123456"
    )


def test_an_unknown_farmer_is_explained_before_submit(monkeypatch):
    profile = importlib.import_module(PACKAGE + ".farmer_reference.profile")
    service = _lookup_service(
        monkeypatch, AsyncMock(side_effect=profile.FarmerReferenceError("FARMER_REFERENCE_NOT_FOUND"))
    )
    code, text = run(service._farmer_problem("s", _farmer_session(_row())))
    assert code == "FARMER_NOT_FOUND"
    assert text.startswith("No farmer with Farmer ID FR-123456789012 and FAN 1234567890123456 is in the Farmer Registry")


def test_a_wrong_pair_is_explained_before_submit(monkeypatch):
    found = SimpleNamespace(profile={"farmer_id": "FR-123456789012", "fayda_fan_id": "9999999999999999"})
    service = _lookup_service(monkeypatch, AsyncMock(return_value=found))
    code, text = run(service._farmer_problem("s", _farmer_session(_row())))
    assert code == "FARMER_IDENTITY_MISMATCH"
    assert text.startswith("The Farmer ID and Fayda ID belong to different farmers in the Farmer Registry")


def test_an_unreachable_registry_is_reported_as_unavailable(monkeypatch):
    profile = importlib.import_module(PACKAGE + ".farmer_reference.profile")
    messages = importlib.import_module(PACKAGE + ".farmer_reference.messages")
    for reference_code in ("FARMER_REFERENCE_LOOKUP_UNAVAILABLE", "FARMER_REFERENCE_LOOKUP_CONFIGURATION_REQUIRED"):
        _native()._answers.clear()
        service = _lookup_service(monkeypatch, AsyncMock(side_effect=profile.FarmerReferenceError(reference_code)))
        code, text = run(service._farmer_problem("s", _farmer_session(_row())))
        assert code == "LOOKUP_UNAVAILABLE"
        assert text == messages.explain(reference_code, {"farmer_id": "FR-123456789012", "fayda_fan_id": "1234567890123456"})


def test_a_signing_failure_is_unavailable_not_an_error(monkeypatch, caplog):
    messages = importlib.import_module(PACKAGE + ".farmer_reference.messages")
    service = _lookup_service(monkeypatch, AsyncMock(side_effect=RuntimeError("key file /secret/x unreadable")))
    code, text = run(service._farmer_problem("s", _farmer_session(_row())))
    assert code == "LOOKUP_UNAVAILABLE"
    assert text == messages.explain(
        "FARMER_REFERENCE_LOOKUP_UNAVAILABLE", {"farmer_id": "FR-123456789012", "fayda_fan_id": "1234567890123456"}
    )
    assert "RuntimeError" in caplog.text and "/secret/x" not in caplog.text


def test_a_matching_pair_has_no_problem(monkeypatch):
    found = SimpleNamespace(profile={"farmer_id": "FR-123456789012", "fayda_fan_id": "1234567890123456"})
    service = _lookup_service(monkeypatch, AsyncMock(return_value=found))
    assert run(service._farmer_problem("s", _farmer_session(_row()))) is None


def test_a_form_already_linked_to_a_farmer_is_left_to_submit(monkeypatch):
    lookup = AsyncMock()
    service = _lookup_service(monkeypatch, lookup)
    assert run(service._farmer_problem("s", _farmer_session(_row(), dependency=_Dependency()))) is None
    lookup.assert_not_called()


# F. record names ------------------------------------------------------------------

def test_the_record_name_migration_follows_the_last_one_and_changes_only_names_still_in_code():
    folder = os.path.join(os.path.dirname(__file__), "..", "..", "docker", "db-seed", "migrations")
    assert "0010_record_names_readable.sql" in sorted(os.listdir(folder))
    with open(os.path.join(folder, "0010_record_names_readable.sql"), encoding="utf-8") as handle:
        text = handle.read()
    assert "pg_temp.plain_code_text(%2$I) <> %2$I" in text


# G. follow-ups: lookup deadline, throttle, messages, registry date --------------------

def _native():
    return importlib.import_module(PACKAGE + ".farmer_reference.native")


def test_a_slow_farmer_registry_is_cut_off_by_one_overall_deadline(monkeypatch):
    messages = importlib.import_module(PACKAGE + ".farmer_reference.messages")
    native = _native()

    async def slow(*args, **kwargs):
        await asyncio.sleep(5)

    monkeypatch.setattr(native, "_VALIDATE_DEADLINE_SECONDS", 0.05)
    monkeypatch.setattr(native, "_answers", {})
    service = _lookup_service(monkeypatch, slow)
    code, text = run(service._farmer_problem("slow", _farmer_session(_row())))
    assert code == "LOOKUP_UNAVAILABLE"
    assert text == messages.explain(
        "FARMER_REFERENCE_LOOKUP_UNAVAILABLE", {"farmer_id": "FR-123456789012", "fayda_fan_id": "1234567890123456"}
    )


def test_a_quick_answer_is_not_cut_off(monkeypatch):
    native = _native()
    monkeypatch.setattr(native, "_answers", {})
    found = SimpleNamespace(profile={"farmer_id": "FR-123456789012", "fayda_fan_id": "1234567890123456"})
    service = _lookup_service(monkeypatch, AsyncMock(return_value=found))
    assert run(service._farmer_problem("quick", _farmer_session(_row()))) is None


def test_repeated_validate_clicks_call_the_farmer_registry_once(monkeypatch):
    native = _native()
    profile = importlib.import_module(PACKAGE + ".farmer_reference.profile")
    monkeypatch.setattr(native, "_answers", {})
    lookup = AsyncMock(side_effect=profile.FarmerReferenceError("FARMER_REFERENCE_NOT_FOUND"))
    service = _lookup_service(monkeypatch, lookup)
    first = run(service._farmer_problem("same", _farmer_session(_row())))
    second = run(service._farmer_problem("same", _farmer_session(_row())))
    assert first == second and first[0] == "FARMER_NOT_FOUND"
    assert lookup.await_count == 1
    run(service._farmer_problem("other", _farmer_session(_row())))
    assert lookup.await_count == 2


def test_a_changed_id_or_an_expired_answer_asks_the_farmer_registry_again(monkeypatch):
    native = _native()
    monkeypatch.setattr(native, "_answers", {})
    found = SimpleNamespace(profile={"farmer_id": "FR-123456789012", "fayda_fan_id": "1234567890123456"})
    lookup = AsyncMock(return_value=found)
    service = _lookup_service(monkeypatch, lookup)
    run(service._farmer_problem("s", _farmer_session(_row())))
    changed = _row()
    changed.fayda_fan_id = "6543210987654321"
    run(service._farmer_problem("s", _farmer_session(changed)))
    assert lookup.await_count == 2
    native._answers.clear()
    monkeypatch.setattr(native, "_ANSWER_SECONDS", -1.0)
    run(service._farmer_problem("s", _farmer_session(changed)))
    run(service._farmer_problem("s", _farmer_session(changed)))
    assert lookup.await_count == 4


def test_remembered_answers_stay_bounded(monkeypatch):
    native = _native()
    monkeypatch.setattr(native, "_answers", {})
    monkeypatch.setattr(native, "_ANSWER_LIMIT", 3)
    for number in range(10):
        native._remember_answer(("s", number), None)
    assert len(native._answers) == 3 and ("s", 9) in native._answers


def test_an_unknown_reference_code_is_logged_and_never_shown(caplog):
    messages = importlib.import_module(PACKAGE + ".farmer_reference.messages")
    with caplog.at_level("WARNING"):
        text = messages.explain("FARMER_REFERENCE_SOMETHING_NEW", {"farmer_id": "FR-1"})
    assert "FARMER_REFERENCE_" not in text
    assert text.startswith("The Farmer Registry check could not be completed.")
    assert "FARMER_REFERENCE_SOMETHING_NEW" in caplog.text


def test_a_known_reference_code_is_not_logged_as_missing(caplog):
    messages = importlib.import_module(PACKAGE + ".farmer_reference.messages")
    with caplog.at_level("WARNING"):
        messages.explain("FARMER_REFERENCE_NOT_FOUND", {"farmer_id": "FR-1"})
    assert "missing" not in caplog.text


def test_the_ear_tag_is_not_quoted_in_the_register_clash_message():
    text = animal.G2PRegisterDomainServiceAnimal._ear_tag_clash_message(
        "ET0000000123", SimpleNamespace(table="register", application_reference=None), None
    )
    assert text.startswith("Ear tag ET0000000123 is already registered") and "'" not in text


def test_business_dates_read_the_registry_date_not_the_server_date():
    late = datetime(2026, 10, 29, 22, 30, tzinfo=UTC)  # already 30 October in Addis Ababa
    with patch.object(local_date, "datetime") as clock:
        clock.now.return_value = late
        expected = date(2026, 10, 30)
        profile = importlib.import_module(PACKAGE + ".farmer_reference.profile")
        assert profile._local_today() == expected
        for module in ("reminder_alert_utils", "vaccination_status_service", "outbreak_alert_service"):
            assert hasattr(importlib.import_module(SERVICES + module), "local_today")
        assert importlib.import_module(SERVICES + "reminder_alert_utils").today() == expected
    # a birth date of the registry's today is accepted, tomorrow is refused
    profile = importlib.import_module(PACKAGE + ".farmer_reference.profile")
    today = date(2026, 10, 30)
    assert profile.local_profile({"birth_date": "2026-10-30"}, today=today)["date_of_birth"] == today
    with pytest.raises(profile.FarmerReferenceError):
        profile.local_profile({"birth_date": "2026-10-31"}, today=today)


def test_the_migration_is_in_the_source_map():
    import json
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[2]
    path = root / "docs" / "refactor" / "SOURCE_MAP.json"
    if not path.exists():
        pytest.skip("source map not mounted")
    sources = {entry["source"] for entry in json.loads(path.read_text(encoding="utf-8"))["files"]}
    assert "docker/db-seed/migrations/0010_record_names_readable.sql" in sources
