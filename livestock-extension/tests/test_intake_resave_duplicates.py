"""Saving an intake section again does not clash with its own earlier rows.

The duplicate checks (ear tag, mortality, disease, health event, breeding) run
against real SQL on an in-memory SQLite database, with the platform pieces the
services import stubbed, so the tests need only SQLAlchemy.
"""

import asyncio
import importlib
import sys
import types
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sa = pytest.importorskip("sqlalchemy")
from sqlalchemy import Column, Date, String, create_engine, select  # noqa: E402
from sqlalchemy.orm import declarative_base, sessionmaker  # noqa: E402

SERVICES = (
    Path(__file__).resolve().parents[1]
    / "src/openg2p_registry_livestock_extension/register_domain/services"
)
PACKAGE = "livestock_resave_under_test"
MODELS = "openg2p_registry_extensions.register_domain.models"
STUBS = ("openg2p_registry_core", "openg2p_registry_core.errors", "openg2p_registry_core.models",
         "openg2p_registry_core.services", "openg2p_registry_extensions",
         "openg2p_registry_extensions.register_domain", MODELS)

def _missing(attr):
    raise AttributeError(attr)


Base = declarative_base()


def table_pair(name, **columns):
    """A register model and the intake model of the same section."""
    register = type(f"G2PRegister{name}", (Base,), {
        "__tablename__": f"register_{name.lower()}",
        "internal_record_id": Column(String, primary_key=True),
        **{key: Column(kind) for key, kind in columns.items()},
    })
    intake = type(f"G2PIntakeForm{name}", (Base,), {
        "__tablename__": f"intake_{name.lower()}",
        "internal_record_id": Column(String, primary_key=True),
        "submission_id": Column(String),
        "application_reference": Column(String),
        **{key: Column(kind) for key, kind in columns.items()},
    })
    return register, intake


ANIMAL = table_pair("Animal", ear_tag_id=String, species=String, breed=String, secondary_identifier=String)
VITAL = table_pair("VitalEvent", ear_tag_id=String, event_type=String, disease_type=String,
                   date_onset=Date, event_date=Date)
HEALTH = table_pair("HealthEvent", ear_tag_id=String, event_type=String, disease_type=String,
                    date_onset=Date, date_resolution=Date)
BREEDING = table_pair("Breeding", ear_tag_id=String, event_type=String, breeding_date=Date)

TAG = "ET0000000013"
OTHER_TAG = "ET0000000099"


@pytest.fixture()
def world(monkeypatch):
    class Refusal(Exception):
        def __init__(self, code=None, message=None):
            super().__init__(message)
            self.message = message

    class Codes:
        class REQUEST_VALIDATION_ERROR:
            value = ("", "REQ-VAL-001")

    def stub(name, **attrs):
        module = types.ModuleType(name)
        module.__dict__.update(attrs)
        module.__path__ = []
        return module

    models = {f"G2P{kind}{name}": model
              for name, (register, intake) in {"Animal": ANIMAL, "VitalEvent": VITAL,
                                               "HealthEvent": HEALTH, "Breeding": BREEDING}.items()
              for kind, model in (("Register", register), ("IntakeForm", intake))}
    def anything(name):
        module = stub(name)
        module.__getattr__ = lambda attr: MagicMock() if not attr.startswith("__") else _missing(attr)
        return module

    stubs = {
        "openg2p_registry_core": stub("openg2p_registry_core"),
        "openg2p_registry_core.errors": stub("openg2p_registry_core.errors",
                                             G2PRegistryErrorCodes=Codes, G2PRegistryException=Refusal),
        "openg2p_registry_core.models": anything("openg2p_registry_core.models"),
        "openg2p_registry_core.services": stub("openg2p_registry_core.services", G2PRegisterDomainService=object),
        "openg2p_registry_extensions": stub("openg2p_registry_extensions"),
        "openg2p_registry_extensions.register_domain": stub("openg2p_registry_extensions.register_domain"),
        MODELS: stub(MODELS, **models),
        PACKAGE: stub(PACKAGE),
    }
    stubs[PACKAGE].__path__ = [str(SERVICES)]
    for name in list(sys.modules):
        if name in STUBS or name == PACKAGE or name.startswith(PACKAGE + "."):
            monkeypatch.delitem(sys.modules, name)
    for name, module in stubs.items():
        monkeypatch.setitem(sys.modules, name, module)

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(engine)()

    utils = importlib.import_module(PACKAGE + ".domain_validation_utils")

    async def find_in_tables(register_model, intake_model, condition_of, search=("register", "intake")):
        for table in search:
            model = {"register": register_model, "intake": intake_model}[table]
            reference = getattr(model, "application_reference", None)
            column = reference if reference is not None else model.internal_record_id
            rows = session.execute(select(column).where(condition_of(model)).limit(1)).all()
            if rows:
                return utils.TableMatch(table, str(rows[0][0]) if reference is not None and rows[0][0] else None)
        return None

    async def exists_in_tables(*args, **kwargs):
        return await find_in_tables(*args, **kwargs) is not None

    monkeypatch.setattr(utils, "find_in_tables", find_in_tables)
    monkeypatch.setattr(utils, "exists_in_tables", exists_in_tables)
    services = {}
    for name, module in (("animal", "g2p_register_domain_service_animal"),
                         ("vital", "g2p_register_domain_service_vital_event"),
                         ("health", "g2p_register_domain_service_health_event"),
                         ("breeding", "g2p_register_domain_service_breeding")):
        loaded = importlib.import_module(f"{PACKAGE}.{module}")
        monkeypatch.setattr(loaded, "exists_in_tables", exists_in_tables, raising=False)
        services[name] = loaded
    yield types.SimpleNamespace(session=session, utils=utils, services=services, Refusal=Refusal)
    session.close()
    Base.metadata.drop_all(engine)


def put(world, model, **values):
    world.session.add(model(**values))
    world.session.commit()


def run(coroutine):
    return asyncio.run(coroutine)


def animal_service(world):
    return world.services["animal"].G2PRegisterDomainServiceAnimal()


def vital_service(world):
    return world.services["vital"].G2PRegisterDomainServiceVitalEvent()


def health_service(world):
    return world.services["health"].G2PRegisterDomainServiceHealthEvent()


def breeding_service(world):
    return world.services["breeding"].G2PRegisterDomainServiceBreeding()


# ear tags -----------------------------------------------------------------

def animal_row(row_id, tag=TAG, **extra):
    return {"internal_record_id": row_id, "ear_tag_id": tag, "species": "CATTLE", "breed": "LOCAL", **extra}


def test_resaving_an_animal_with_the_id_it_is_stored_under_passes(world):
    put(world, ANIMAL[1], internal_record_id="a-1", submission_id="s-1", ear_tag_id=TAG,
        species="CATTLE", breed="LOCAL", application_reference="REF-1")
    run(animal_service(world)._validate_no_duplicate_ear_tags([animal_row("a-1")]))


def test_resaving_an_animal_with_an_id_the_intake_table_does_not_hold_passes(world):
    put(world, ANIMAL[1], internal_record_id="a-stored", submission_id="s-1", ear_tag_id=TAG,
        species="CATTLE", breed="LOCAL", application_reference="REF-1")
    run(animal_service(world)._validate_no_duplicate_ear_tags([animal_row("a-sent")]))


def test_the_same_ear_tag_in_another_intake_is_still_refused_after_the_save(world):
    put(world, ANIMAL[1], internal_record_id="a-other", submission_id="s-2", ear_tag_id=TAG,
        species="CATTLE", breed="LOCAL", application_reference="REF-2")
    put(world, ANIMAL[1], internal_record_id="a-1", submission_id="s-1", ear_tag_id=TAG,
        species="CATTLE", breed="LOCAL", application_reference="REF-1")
    with pytest.raises(world.Refusal) as refused:
        run(animal_service(world)._validate_no_duplicate_ear_tags(
            [animal_row("a-1")], search=("intake",), exclude_submission_ids={"s-1"}))
    assert "another intake form" in refused.value.message


def test_the_same_ear_tag_in_the_register_is_still_refused_on_a_resave(world):
    put(world, ANIMAL[0], internal_record_id="reg-1", ear_tag_id=TAG, species="CATTLE", breed="LOCAL")
    with pytest.raises(world.Refusal) as refused:
        run(animal_service(world)._validate_no_duplicate_ear_tags([animal_row("a-sent")]))
    assert "already registered" in refused.value.message


def test_editing_an_approved_animal_is_not_flagged_against_itself(world):
    put(world, ANIMAL[0], internal_record_id="reg-1", ear_tag_id=TAG, species="CATTLE", breed="LOCAL")
    run(animal_service(world)._validate_no_duplicate_ear_tags([animal_row("reg-1")]))


def test_a_change_request_still_meets_a_tag_drafted_in_an_intake(world):
    put(world, ANIMAL[0], internal_record_id="reg-1", ear_tag_id=OTHER_TAG, species="CATTLE", breed="LOCAL")
    put(world, ANIMAL[1], internal_record_id="a-draft", submission_id="s-2", ear_tag_id=TAG,
        species="CATTLE", breed="LOCAL", application_reference="REF-2")
    with pytest.raises(world.Refusal):
        run(animal_service(world)._validate_no_duplicate_ear_tags([animal_row("reg-1", tag=TAG)]))


def test_two_rows_of_one_save_with_the_same_tag_are_refused(world):
    with pytest.raises(world.Refusal):
        run(animal_service(world)._validate_no_duplicate_ear_tags([animal_row("a-1"), animal_row("a-2")]))


# mortality ------------------------------------------------------------------

def mortality_row(row_id, tag=TAG):
    return {"internal_record_id": row_id, "ear_tag_id": tag, "event_type": "MORTALITY"}


def test_resaving_a_mortality_event_passes(world):
    put(world, VITAL[1], internal_record_id="v-stored", submission_id="s-1", ear_tag_id=TAG,
        event_type="MORTALITY", application_reference="REF-1")
    run(vital_service(world)._validate_no_duplicate_mortality([mortality_row("v-sent")]))
    run(vital_service(world)._validate_no_duplicate_mortality(
        [mortality_row("v-stored")], search=("intake",), exclude_submission_ids={"s-1"}))


def test_a_second_mortality_on_the_animal_in_another_row_is_refused(world):
    with pytest.raises(world.Refusal) as refused:
        run(vital_service(world)._validate_no_duplicate_mortality([mortality_row("v-1"), mortality_row("v-2")]))
    assert "mortality event already exists" in refused.value.message


def test_a_mortality_in_another_intake_or_the_register_is_still_refused(world):
    put(world, VITAL[1], internal_record_id="v-other", submission_id="s-2", ear_tag_id=TAG,
        event_type="MORTALITY", application_reference="REF-2")
    with pytest.raises(world.Refusal):
        run(vital_service(world)._validate_no_duplicate_mortality(
            [mortality_row("v-1")], search=("intake",), exclude_submission_ids={"s-1"}))
    put(world, VITAL[0], internal_record_id="v-reg", ear_tag_id=OTHER_TAG, event_type="MORTALITY")
    with pytest.raises(world.Refusal):
        run(vital_service(world)._validate_no_duplicate_mortality([mortality_row("v-9", tag=OTHER_TAG)]))


def test_resaving_a_disease_event_passes_and_a_namesake_elsewhere_is_refused(world):
    put(world, VITAL[1], internal_record_id="v-stored", submission_id="s-1", ear_tag_id=TAG,
        event_type="DISEASE", disease_type="anthrax", date_onset=date(2026, 10, 1))
    row = {"internal_record_id": "v-sent", "ear_tag_id": TAG, "event_type": "DISEASE",
           "disease_type": "Anthrax", "date_onset": "2026-10-01"}
    run(vital_service(world)._validate_no_duplicate_disease([row]))
    put(world, VITAL[1], internal_record_id="v-other", submission_id="s-2", ear_tag_id=TAG,
        event_type="DISEASE", disease_type="anthrax", date_onset=date(2026, 10, 1))
    with pytest.raises(world.Refusal):
        run(vital_service(world)._validate_no_duplicate_disease(
            [row], search=("intake",), exclude_submission_ids={"s-1"}))


# health events ---------------------------------------------------------------

def test_resaving_a_health_event_passes_and_another_intake_is_refused(world):
    put(world, HEALTH[1], internal_record_id="h-stored", submission_id="s-1", ear_tag_id=TAG,
        event_type="DISEASE", disease_type="anthrax", date_onset=date(2026, 10, 1))
    row = {"internal_record_id": "h-sent", "ear_tag_id": TAG, "event_type": "DISEASE",
           "disease_type": "anthrax", "date_onset": "2026-10-01"}
    run(health_service(world)._validate_no_duplicate_events([row]))
    put(world, HEALTH[1], internal_record_id="h-other", submission_id="s-2", ear_tag_id=TAG,
        event_type="DISEASE", disease_type="anthrax", date_onset=date(2026, 10, 1))
    with pytest.raises(world.Refusal):
        run(health_service(world)._validate_no_duplicate_events(
            [row], search=("intake",), exclude_submission_ids={"s-1"}))


# breeding -------------------------------------------------------------------

def test_resaving_a_breeding_event_passes_and_a_second_one_in_the_cycle_is_refused(world):
    put(world, BREEDING[1], internal_record_id="b-stored", submission_id="s-1", ear_tag_id=TAG,
        event_type="AI", breeding_date=date(2026, 10, 1))
    row = {"internal_record_id": "b-sent", "ear_tag_id": TAG, "event_type": "AI", "breeding_date": "2026-10-01"}
    run(breeding_service(world)._validate_no_duplicate_breeding([row]))
    run(breeding_service(world)._validate_no_duplicate_breeding(
        [dict(row, internal_record_id="b-stored")], search=("intake",), exclude_submission_ids={"s-1"}))
    put(world, BREEDING[0], internal_record_id="b-reg", ear_tag_id=TAG, event_type="AI",
        breeding_date=date(2026, 10, 10))
    with pytest.raises(world.Refusal) as refused:
        run(breeding_service(world)._validate_no_duplicate_breeding([row]))
    assert "Another AI event already exists" in refused.value.message
