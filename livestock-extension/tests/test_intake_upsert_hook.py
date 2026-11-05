"""The intake service runs the domain service's post_intake_upsert after a section save."""

import asyncio
import importlib
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

pytest.importorskip("openg2p_registry_core")

from openg2p_registry_core.errors import G2PRegistryException

PACKAGE = os.environ.get("REGISTRY_EXTENSION_MODULE", "openg2p_registry_livestock_extension")
hook_module = importlib.import_module(PACKAGE + ".intake_upsert_hook")

SUBMISSION = "sub-1"
EVENTS = "11111111-0000-4000-8000-000000000001"


class PlatformStandIn:
    """The platform save, reduced to what the hook reads around it."""

    def __init__(self, rows, existing=()):
        self.rows = rows
        self.existing = {row_id: object() for row_id in existing}
        self.saved = []

    async def save_intake_form_submission_with_session(
        self, submission_id, section_id, section_payload, section_register_id,
        form_id, register_id, created_by, session, documents=None,
    ):
        self.saved.append(section_id)
        return SimpleNamespace(submission_id=SUBMISSION)

    async def _get_register_definition(self, register_id, session):
        return SimpleNamespace(register_mnemonic="HealthEvent")

    async def _resolve_intake_form_class(self, register_id, session):
        return object

    async def _get_intake_rows_list(self, intake_class, submission_id, session):
        assert submission_id == SUBMISSION
        return self.rows

    async def _get_intake_rows(self, intake_class, submission_id, session):
        return dict(self.existing)


class Service(hook_module.IntakeUpsertHook, PlatformStandIn):
    pass


def session():
    return SimpleNamespace(flush=AsyncMock())


def save(service, db):
    return asyncio.run(service.save_intake_form_submission_with_session(
        None, "health", [{"ear_tag_id": "ET0101010101"}], EVENTS, "form", "root", "user", db))


def with_domain_service(domain_service):
    factory = SimpleNamespace(get_domain_service=lambda mnemonic: domain_service)
    return patch.object(hook_module.G2PRegisterDomainFactory, "get_component", return_value=factory)


def test_saved_rows_of_the_submission_reach_post_intake_upsert():
    rows = [SimpleNamespace(submission_id=SUBMISSION, ear_tag_id="ET0101010101")]
    domain_service = SimpleNamespace(post_intake_upsert=AsyncMock())
    service, db = Service(rows), session()
    with with_domain_service(domain_service):
        submission = save(service, db)
    assert submission.submission_id == SUBMISSION
    assert service.saved == ["health"]
    domain_service.post_intake_upsert.assert_awaited_once_with(rows, db)
    db.flush.assert_awaited()


def test_a_refusal_from_the_domain_service_fails_the_save():
    refusal = G2PRegistryException(code="G2P-REG-400", message="'ET0101010101' is not an animal of this submission.")
    domain_service = SimpleNamespace(post_intake_upsert=AsyncMock(side_effect=refusal))
    service = Service([SimpleNamespace(submission_id=SUBMISSION)])
    with with_domain_service(domain_service), pytest.raises(G2PRegistryException) as raised:
        save(service, session())
    assert "not an animal of this submission" in raised.value.message


def test_a_register_without_the_hook_saves_as_before():
    service, db = Service([SimpleNamespace(submission_id=SUBMISSION)]), session()
    with with_domain_service(SimpleNamespace()):
        assert save(service, db).submission_id == SUBMISSION
    with with_domain_service(None):
        assert save(service, db).submission_id == SUBMISSION
    db.flush.assert_not_awaited()


def test_no_rows_left_after_the_save_skips_the_hook():
    domain_service = SimpleNamespace(post_intake_upsert=AsyncMock())
    with with_domain_service(domain_service):
        save(Service([]), session())
    domain_service.post_intake_upsert.assert_not_awaited()


def test_only_the_rows_of_this_save_reach_the_hook():
    # r-old was there before and is not in this save; r-sent comes back in the
    # payload; r-new is inserted by this save.
    def row(row_id):
        return SimpleNamespace(submission_id=SUBMISSION, internal_record_id=row_id)

    domain_service = SimpleNamespace(post_intake_upsert=AsyncMock())
    service = Service([row("r-old"), row("r-sent"), row("r-new")], existing=("r-old", "r-sent"))
    payload = [{"internal_record_id": "r-sent", "ear_tag_id": "ET0101010101", "edit_action": "UPDATE"},
               {"ear_tag_id": "ET0101010102", "edit_action": "ADD"}]
    with with_domain_service(domain_service):
        asyncio.run(service.save_intake_form_submission_with_session(
            SUBMISSION, "health", payload, EVENTS, "form", "root", "user", session()))
    sent = domain_service.post_intake_upsert.await_args.args[0]
    assert [r.internal_record_id for r in sent] == ["r-sent", "r-new"]


def test_a_deleted_row_is_not_counted_as_saved():
    assert hook_module.saved_row_ids([
        {"internal_record_id": "a", "edit_action": "UPDATE"},
        {"internal_record_id": "b", "edit_action": "DELETE"},
        {"ear_tag_id": "ET0101010101", "edit_action": "ADD"},
    ]) == {"a"}


def test_the_intake_service_runs_the_hook_after_the_required_field_check():
    native = importlib.import_module(PACKAGE + ".farmer_reference.native")
    required = importlib.import_module(PACKAGE + ".required_intake")
    order = native.ReferenceIntakeService.__mro__
    assert order.index(required.RequiredFieldsMixin) < order.index(hook_module.IntakeUpsertHook)
    assert order.index(hook_module.IntakeUpsertHook) < order.index(native.G2PIntakeFormDataService)


def utils_module():
    return importlib.import_module(PACKAGE + ".register_domain.services.domain_validation_utils")


def test_the_domain_checks_read_through_the_saving_session_and_release_it():
    utils, db, seen = utils_module(), session(), []

    async def post_intake_upsert(rows, given):
        seen.append((utils.ingest_session.get(), given))

    with with_domain_service(SimpleNamespace(post_intake_upsert=post_intake_upsert)):
        save(Service([SimpleNamespace(submission_id=SUBMISSION)]), db)
    assert seen == [(db, db)]
    assert utils.ingest_session.get() is None


def test_the_session_is_released_when_the_domain_service_refuses():
    utils = utils_module()
    refusal = G2PRegistryException(code="G2P-REG-400", message="refused")
    domain_service = SimpleNamespace(post_intake_upsert=AsyncMock(side_effect=refusal))
    with with_domain_service(domain_service), pytest.raises(G2PRegistryException):
        save(Service([SimpleNamespace(submission_id=SUBMISSION)]), session())
    assert utils.ingest_session.get() is None


def test_ear_tag_exists_sees_an_animal_flushed_in_the_saving_session():
    utils = utils_module()
    db = SimpleNamespace(execute=AsyncMock(side_effect=[
        SimpleNamespace(scalar=lambda: False), SimpleNamespace(scalar=lambda: True)]))
    columns = SimpleNamespace(ear_tag_id=None, secondary_identifier=None)

    async def run():
        token = utils.ingest_session.set(db)
        try:
            return await utils.ear_tag_exists("ET0101010101")
        finally:
            utils.ingest_session.reset(token)

    with patch.object(utils, "_animal_models", return_value=(columns, columns)):
        with patch.object(utils, "animal_identified_by", return_value=True):
            assert asyncio.run(run()) is True
    assert db.execute.await_count == 2
