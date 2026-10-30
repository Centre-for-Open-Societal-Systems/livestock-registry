"""The db-seed sample loader: each sample person is found in the registry's own Farmer references by Fayda
number (the Farmer ID is the Farmer registry's, never invented), their livestock is entered as an intake and
approved at both stages by the sample approvers, and the database is only read."""

import ast
import importlib.util
import itertools
import re
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "docker/db-seed"


@pytest.fixture(scope="module")
def loader():
    extras = types.ModuleType("psycopg2.extras")
    extras.Json = lambda value: ("json", value)
    stubs = {"psycopg2": types.ModuleType("psycopg2"), "psycopg2.extras": extras}
    saved = {name: sys.modules.get(name) for name in stubs}
    sys.modules.update(stubs)
    try:
        spec = importlib.util.spec_from_file_location("livestock_sample_loader", SEED / "load_sample_data.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        yield module
    finally:
        for name, module in saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


def test_loader_signs_in_like_the_portal_and_never_writes_to_the_database():
    source = (SEED / "load_sample_data.py").read_text(encoding="utf-8")
    code = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("#"))
    for forbidden in ("grant_type", "KEYCLOAK_ADMIN", "admin-cli", "/admin/realms", "directAccessGrants",
                      "/approve_change_request"):
        assert forbidden not in code, forbidden
    # No database write of any kind: no statement that changes data, and a read-only connection.
    assert not re.findall(r"\b(INSERT\s+INTO|UPDATE\s+[\"\w.]+\s+SET|DELETE\s+FROM|TRUNCATE|DROP\s|ALTER\s+TABLE|\.commit\()",
                          code, re.IGNORECASE)
    # The read-only session is the real guard: the database refuses a write whatever the text says.
    assert "readonly=True" in code
    assert "backfill_functional_ids" not in code and "ensure_farmer" not in code and "def link" not in code
    # The Farmer reference is only read, and no Farmer ID is invented or read from the pack.
    assert "FROM coss_farmer_references" in code
    assert "farmer_ids.json" not in code and not re.search(r"FR-\d", source)
    for required in ("/auth/start_authentication_transaction", "kc-form-login", "/auth/callback",
                     "/intake-form-data/finalize_intake_form_submission", "/awe/submit_task_decision",
                     "INTAKE_SEED_APPROVER_1", "INTAKE_SEED_APPROVER_2", "INTAKE_SEED_PASSWORD"):
        assert required in code, required
    imported = {a.name.split(".")[0] for node in ast.walk(ast.parse(source))
                if isinstance(node, ast.Import) for a in node.names}
    assert not imported & {"requests", "httpx", "keycloak"}


def test_the_image_carries_the_loader_and_the_pinned_pack():
    dockerfile = (SEED / "Dockerfile").read_text(encoding="utf-8")
    assert "ARG OPENG2P_DATA_REPO=https://github.com/Centre-for-Open-Societal-Systems/openg2p-data.git" in dockerfile
    assert "docker/db-seed/load_sample_data.py /seed/" in dockerfile
    assert dockerfile.index("load_sample_data.py") > dockerfile.index("rm -rf /seed/")


PLACES = {
    "ET": {"level_value_id": "ET", "level_id": "l0", "level_value_mnemonic": "Ethiopia", "parent_level_value_id": None},
    "ET01": {"level_value_id": "ET01", "level_id": "l1", "level_value_mnemonic": "Tigray",
             "parent_level_value_id": "ET"},
    "ET0101": {"level_value_id": "ET0101", "level_id": "l2", "level_value_mnemonic": "North Western",
               "parent_level_value_id": "ET01"},
    "ET010101": {"level_value_id": "ET010101", "level_id": "l3", "level_value_mnemonic": "Tahtay Adiyabo",
                 "parent_level_value_id": "ET0101"},
    "ET01010102": {"level_value_id": "ET01010102", "level_id": "l4", "level_value_mnemonic": "Badme",
                   "parent_level_value_id": "ET010101"},
}
PEOPLE = [
    {"individual_id": "ETH-IND-0001", "given_name": "Berhanu", "fathers_name": "Abebe", "gender": "MALE",
     "birth_date": "1984-08-06", "phone": "+251941923320", "national_id": "502628318720",
     "geo_pcode": "ET01010102", "latitude": 14.4, "longitude": 37.7},
    {"individual_id": "ETH-IND-0002", "given_name": "Tsehay", "fathers_name": "Kebede", "gender": "FEMALE",
     "birth_date": "1988-02-29", "phone": "+251911000002", "national_id": "721996394985",
     "geo_pcode": "ET01010102", "latitude": 14.4, "longitude": 37.7},
]
# The Farmer IDs the Farmer registry generated, as the Farmer references in this registry carry them.
REFERENCES = {"502628318720": "FR-209610506580", "721996394985": "FR-579834743732"}
HERDS = [
    {"individual_id": "ETH-IND-0001",
     "survey_personnel": {"surveyor_name": "Hailu Gebre", "surveyor_mobile_number": "0911223344"},
     "location": {"latitude": 14.4, "longitude": 37.7},
     "animals": [{"ear_tag_id": "ET 0001 01", "species": "LSTK_CATTLE", "breed": "BREED_LOCAL", "quantity": 1,
                  "gender": "FEMALE", "health_status": "SICK", "vaccination_status": "OVERDUE",
                  "registration_date": "2026-03-01"}],
     "health_events": [{"ear_tag_id": "ET 0001 01", "species": "LSTK_CATTLE", "event_type": "DISEASE"}],
     "breeding": [{"ear_tag_id": "ET 0001 01", "species": "LSTK_CATTLE", "event_type": "AI"}]},
    {"individual_id": "ETH-IND-0002",
     "animals": [{"ear_tag_id": "ET 0002 01", "species": "LSTK_GOAT", "breed": "BREED_LOCAL", "quantity": 4,
                  "gender": "Mixed / Not Applicable", "health_status": "HEALTHY",
                  "vaccination_status": "UP_TO_DATE", "registration_date": "2026-04-01"}]},
]


def plan(loader, herds=HERDS, people=PEOPLE):
    ids = (f"id-{n}" for n in itertools.count(1))
    return loader.plan(people, herds, PLACES, new_id=lambda: next(ids))


def test_each_person_is_one_livestock_intake_with_their_animals_and_events(loader):
    planned = plan(loader)
    assert [[s["form"] for s in p["stages"]] for p in planned] == [["Livestock Intake"], ["Livestock Intake"]]
    stage = planned[0]["stages"][0]
    root, sections = stage["root"], stage["sections"]
    assert list(sections) == ["livestock_farmer_lookup", "livestock_survey_personnel_section_02",
                              "livestock_livestock_location_section_03", "livestock_animal_details_section_01",
                              "livestock_health_event_details_section_01", "livestock_breeding_details_section_01"]
    assert sections["livestock_farmer_lookup"] == [{"internal_record_id": root, "fayda_id": "502628318720"}]  # no Farmer ID yet
    assert sections["livestock_survey_personnel_section_02"][0]["surveyor_name"] == "Hailu Gebre"
    animal = sections["livestock_animal_details_section_01"][0]
    assert animal["link_internal_record_id"] == root and animal["registration_date"] == "2026-03-01"
    other = planned[1]["stages"][0]["sections"]
    assert "livestock_survey_personnel_section_02" in other
    # A person without coordinates in the pack still gets the Location section: the form requires the hierarchy.
    assert other["livestock_livestock_location_section_03"][0]["geo_lowest_level_value_id"] == "ET01010102"


def test_a_person_is_identified_by_the_fayda_number_with_birth_date_and_gender_and_carries_no_farmer_id(loader):
    planned = plan(loader)
    person = planned[0]
    assert person["foundational_id"] == "502628318720"
    assert (person["birth_date"], person["gender"]) == ("1984-08-06", "MALE")
    assert "farmer_id" not in person and "farmer" not in person
    assert "FR-" not in repr([(p, [s["sections"] for s in p["stages"]]) for p in planned])


@pytest.mark.parametrize("change, message", [
    ({"herds": [{**HERDS[1], "individual_id": "ETH-IND-0099"}]}, "not a sample person"),
    ({"herds": [{**HERDS[1], "animals": []}]}, "no animals"),
    ({"people": [PEOPLE[0], {**PEOPLE[1], "national_id": None}]}, "no Fayda ID"),
    ({"people": [PEOPLE[0], {**PEOPLE[1], "geo_pcode": "ET99"}]}, "pack's geography"),
])
def test_bad_samples_fail(loader, change, message):
    with pytest.raises(RuntimeError, match=message):
        plan(loader, **change)


_LOADER = []


class FakeRegistry:
    def __init__(self, previous=None, references=None):
        self.previous = dict(previous or {})
        self.references = REFERENCES if references is None else dict(references)
        self.status, self.waited, self.pending, self.looked_up, self.failures = {}, [], [], [], {}
        self.unprocessed = set()

    def ingest_failure(self, submission_id):
        return self.failures.get(submission_id)

    def ingest_pending(self, submission_id):
        return submission_id in self.unprocessed

    def farmer_reference(self, fayda_id, birth_date, gender, individual_id=None):
        self.looked_up.append((fayda_id, birth_date, gender))
        if fayda_id not in self.references:
            raise _LOADER[0].ReferencePending(f"no farmer reference for Fayda number {fayda_id} yet")
        return {"reference_id": f"ref-{fayda_id}", "farmer_id": self.references[fayda_id], "local_farmer_id": "local"}

    def stage_intakes(self, form_id, fin, root):
        return self.previous.get(fin, [])

    def approval_status(self, submission_id):
        return self.status.get(submission_id)

    def wait_for(self, table, record_id, timeout, submission_id=None):
        self.waited.append((table, record_id))


class FakeApprover:
    """An approver whose task list holds one open task at its stage for every pending intake."""

    def __init__(self, name, stage, registry, calls):
        self.username, self.stage, self.registry, self.calls = name, stage, registry, calls

    def post(self, path, payload, once=False):
        self.calls.append((self.username, path))
        decided = getattr(self.registry, "decided", set())
        self.registry.decided = decided
        if path == "/awe/list_my_tasks":
            if payload["status"] != "open":
                return {"data": {"items": []}}
            return {"data": {"items": [{"id": f"task-{sid}-{self.stage}", "artifact_id": sid,
                                        "stage_order": self.stage} for sid in self.registry.pending
                                       if (sid, self.stage) not in decided
                                       and (self.stage == 1 or (sid, 1) in decided)]}}
        if path == "/awe/submit_task_decision":
            assert payload["current_stage"] == self.stage and payload["action"] == "approve"
            decided.add((payload["artifact_id"], self.stage))
            if self.stage == 2:
                self.registry.status[payload["artifact_id"]] = "APPROVED"
        return {}


def run(loader, registry):
    _LOADER[:] = [loader]
    calls, submitted = [], []
    runner = loader.Loader.__new__(loader.Loader)
    runner.registry, runner.approve_timeout, runner.ingest_timeout = registry, 5, 5
    runner.submitter = types.SimpleNamespace(username="alex.carter")
    runner.approvers = [FakeApprover("alex.carter", 1, registry, calls), FakeApprover("nina.patel", 2, registry, calls)]
    runner.forms = {form: ("form-livestock", "register", {}) for form, _, _ in loader.STAGES}

    def submit(stage, draft=None):
        if draft:
            submitted.append(("draft", draft))
            registry.pending.append(draft)
            return draft
        sid = f"sub-{len(submitted) + 1}"
        submitted.append(("new", stage["sections"]["livestock_farmer_lookup"][0]["farmer_id"]))
        registry.pending.append(sid)
        return sid

    runner.submit = submit
    return runner.run(plan(loader)), submitted, calls


def test_every_farmer_is_found_by_fayda_number_and_every_intake_approved_at_stage_1_then_stage_2(loader):
    registry = FakeRegistry()
    done, submitted, calls = run(loader, registry)
    assert done == {**dict.fromkeys(loader.COUNTERS, 0), "farmers referenced": 2, "intakes submitted": 2,
                    "intakes approved and in the register": 2}
    assert registry.looked_up == [("502628318720", "1984-08-06", "MALE"), ("721996394985", "1988-02-29", "FEMALE")]
    assert submitted == [("new", REFERENCES["502628318720"]), ("new", REFERENCES["721996394985"])]
    decisions = [c for c in calls if c[1] == "/awe/submit_task_decision"]
    assert decisions == [("alex.carter", "/awe/submit_task_decision"), ("nina.patel", "/awe/submit_task_decision")] * 2
    assert [t for t, _ in registry.waited] == ["g2p_register_livestocks"] * 2


def test_nobody_is_loaded_before_their_farmer_reference_arrives(loader):
    registry = FakeRegistry(references={})
    done, submitted, calls = run(loader, registry)
    assert submitted == [] and calls == [] and done["farmers waiting for their farmer reference"] == 2
    assert done["farmers failed"] == 0 and done["farmers referenced"] == 0
    assert done["intakes left for the next run"] == 2


def test_a_rerun_skips_approved_intakes_and_resumes_waiting_ones(loader):
    second = plan(loader)[1]["stages"][0]["root"]
    registry = FakeRegistry(previous={
        "502628318720": [("sub-old", "FINAL", "APPROVED", "root-old")],
        "721996394985": [("sub-wait", "FINAL", "PENDING", second)],
    })
    registry.pending = ["sub-wait"]
    done, submitted, _ = run(loader, registry)
    assert done == {**dict.fromkeys(loader.COUNTERS, 0), "farmers referenced": 2, "intakes resumed at approval": 1,
                    "intakes already approved": 1, "intakes approved and in the register": 1}
    assert submitted == [] and ("g2p_register_livestocks", second) in registry.waited


class ReadOnlyRegistry:
    """Registry.farmer_reference over scripted query answers: the reference rows, then the farmer copy."""

    def __init__(self, loader, references, copy=None):
        self.statements, self.references, self.copy = [], references, copy
        self.farmer_reference = loader.Registry.farmer_reference.__get__(self)

    def rows(self, sql, params=()):
        self.statements.append((" ".join(sql.split()), params))
        if "FROM coss_farmer_references" in sql:
            return self.references
        return [self.copy] if self.copy else []


def test_an_approved_reference_gives_its_generated_farmer_id_by_fayda_number(loader):
    registry = ReadOnlyRegistry(loader, [("ref-1", "FR-209610506580", "local-1", "APPROVED", "src-ref-1")],
                                copy=("1984-08-06", "MALE"))
    got = registry.farmer_reference("502628318720", "1984-08-06", "MALE")
    assert got == {"reference_id": "ref-1", "farmer_id": "FR-209610506580", "local_farmer_id": "local-1"}
    assert registry.statements[0][1] == ("502628318720",)  # found by the Fayda number, never by name
    assert all(sql.startswith("SELECT") for sql, _ in registry.statements)


def test_a_missing_or_pending_reference_is_pending_not_failed(loader):
    with pytest.raises(loader.ReferencePending, match="no farmer reference"):
        ReadOnlyRegistry(loader, []).farmer_reference("502628318720", "1984-08-06", "MALE")
    with pytest.raises(loader.ReferencePending, match="PENDING, not APPROVED"):
        ReadOnlyRegistry(loader, [("ref-1", "FR-1", "local-1", "PENDING", "src-ref-1")]).farmer_reference(
            "502628318720", None, None)
    with pytest.raises(loader.ReferencePending, match="not in the register yet"):
        ReadOnlyRegistry(loader, [("ref-1", "FR-1", "local-1", "APPROVED", "src-ref-1")]).farmer_reference(
            "502628318720", None, None)


@pytest.mark.parametrize("rows, copy, message", [
    ([("ref-1", "FR-1", "local-1", "REJECTED", "src-ref-1")], None, "REJECTED, not APPROVED"),
    ([("ref-1", "FR-1", "local-1", "APPROVED", "src-ref-1"), ("ref-2", "FR-2", "local-2", "APPROVED", "src-ref-2")], None, "more than one"),
    ([("ref-1", "FR-1", "local-1", "APPROVED", "src-ref-1")], ("1990-01-01", "MALE"), "birth date"),
    ([("ref-1", "FR-1", "local-1", "APPROVED", "src-ref-1")], ("1984-08-06", "FEMALE"), "gender"),
])
def test_a_wrong_or_ambiguous_reference_is_refused(loader, rows, copy, message):
    with pytest.raises(RuntimeError, match=message) as error:
        ReadOnlyRegistry(loader, rows, copy).farmer_reference("502628318720", "1984-08-06", "MALE")
    assert not isinstance(error.value, loader.ReferencePending)


def test_gender_is_compared_by_its_first_letter_and_a_date_by_its_day(loader):
    registry = ReadOnlyRegistry(loader, [("ref-1", "FR-1", "local-1", "APPROVED", "src-ref-1")],
                                copy=("1984-08-06 00:00:00", "m"))
    assert registry.farmer_reference("502628318720", "1984-08-06", "MALE")["farmer_id"] == "FR-1"


def test_the_reference_is_looked_up_in_the_configured_farmer_source_only(loader, monkeypatch):
    monkeypatch.delenv("FARMER_REFERENCE_SOURCE_SYSTEM", raising=False)
    monkeypatch.setenv("COSS_FARMER_SOURCE_ID", "farmer-source")
    registry = ReadOnlyRegistry(loader, [("ref-1", "FR-209610506580", "local-1", "APPROVED", "src-1")],
                                copy=("1984-08-06", "MALE"))
    registry.farmer_reference("502628318720", "1984-08-06", "MALE", "ETH-IND-0001")
    sql, params = registry.statements[0]
    assert "source_system = %s" in sql and params == ("502628318720", "farmer-source")
    assert "ORDER BY (state = 'APPROVED') DESC" in sql


def test_a_reference_an_earlier_loader_wrote_is_not_a_farmer_reference(loader, monkeypatch):
    monkeypatch.delenv("FARMER_REFERENCE_SOURCE_SYSTEM", raising=False)
    monkeypatch.delenv("COSS_FARMER_SOURCE_ID", raising=False)
    stale = ("ref-old", "FR-STALE", "local-old", "APPROVED", "ETH-IND-0001")  # source record id = the individual
    with pytest.raises(loader.ReferencePending, match="earlier sample loader"):
        ReadOnlyRegistry(loader, [stale]).farmer_reference("502628318720", None, None, "ETH-IND-0001")
    real = ("ref-new", "FR-209610506580", "local-new", "APPROVED", "uuid-in-farmer-registry")
    got = ReadOnlyRegistry(loader, [stale, real], copy=("1984-08-06", "MALE")).farmer_reference(
        "502628318720", "1984-08-06", "MALE", "ETH-IND-0001")
    assert got["farmer_id"] == "FR-209610506580"


def test_references_of_one_farmer_from_two_sources_agree_and_pending_never_wins_over_approved(loader):
    rows = [("ref-1", "FR-1", "local-1", "APPROVED", "a"), ("ref-2", "FR-1", "local-2", "APPROVED", "b")]
    assert ReadOnlyRegistry(loader, rows, copy=("1984-08-06", "MALE")).farmer_reference(
        "502628318720", "1984-08-06", "MALE")["farmer_id"] == "FR-1"
    rows = [("ref-1", "FR-1", "local-1", "PENDING", "a"), ("ref-2", "FR-1", "local-2", "APPROVED", "b")]
    assert ReadOnlyRegistry(loader, rows, copy=("1984-08-06", "MALE")).farmer_reference(
        "502628318720", "1984-08-06", "MALE")["reference_id"] == "ref-2"


@pytest.mark.parametrize("copy, message", [((None, "MALE"), "no birth date"), (("1984-08-06", None), "no gender"),
                                           (("1984-08-06", ""), "no gender")])
def test_a_missing_birth_date_or_gender_on_the_farmer_is_a_mismatch(loader, copy, message):
    registry = ReadOnlyRegistry(loader, [("ref-1", "FR-1", "local-1", "APPROVED", "src")], copy=copy)
    with pytest.raises(RuntimeError, match=message) as error:
        registry.farmer_reference("502628318720", "1984-08-06", "MALE")
    assert not isinstance(error.value, loader.ReferencePending)


def test_the_connection_is_read_only(loader, monkeypatch):
    seen = {}

    class Conn:
        def set_session(self, **kwargs):
            seen.update(kwargs)

    fake = types.ModuleType("psycopg2")
    fake.connect = lambda **kwargs: Conn()
    monkeypatch.setitem(sys.modules, "psycopg2", fake)
    for name in ("PGHOST", "PGDATABASE", "PGUSER", "PGPASSWORD"):
        monkeypatch.setenv(name, "x")
    loader.Registry()
    assert seen == {"readonly": True, "autocommit": True}


KEYCLOAK_TOKEN = "https://keycloak.example.org/realms/staff/protocol/openid-connect/token"


@pytest.mark.parametrize("environ, expected", [
    ({"STAFF_IAM_URL": "https://iam.example.org", "STAFF_TOKEN_URL": KEYCLOAK_TOKEN}, "https://iam.example.org"),
    ({"STAFF_TOKEN_URL": KEYCLOAK_TOKEN}, "https://staff-iam.example.org"),
    ({"STAFF_TOKEN_URL": "https://keycloak.registry.example.org/realms/staff/protocol/openid-connect/token"},
     "https://staff-iam.registry.example.org"),
])
def test_staff_iam_is_the_public_host_next_to_keycloak(loader, monkeypatch, environ, expected):
    for name in ("STAFF_IAM_URL", "STAFF_TOKEN_URL"):
        monkeypatch.delenv(name, raising=False)
    for name, value in environ.items():
        monkeypatch.setenv(name, value)
    assert loader.staff_iam_url() == expected


@pytest.mark.parametrize("token_url", [None, "https://auth.example.org/realms/staff/protocol/openid-connect/token"])
def test_staff_iam_needs_the_address_when_keycloak_is_not_keycloak_domain(loader, monkeypatch, token_url):
    monkeypatch.delenv("STAFF_IAM_URL", raising=False)
    monkeypatch.delenv("STAFF_TOKEN_URL", raising=False)
    if token_url:
        monkeypatch.setenv("STAFF_TOKEN_URL", token_url)
    with pytest.raises(RuntimeError):
        loader.staff_iam_url()


class FlakyOpener:
    """Answers with the given outcomes in turn: an exception to raise, or a status code."""

    def __init__(self, *outcomes):
        self.outcomes, self.calls = list(outcomes), 0

    def open(self, request, timeout):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        if outcome >= 400:
            raise __import__("urllib.error").error.HTTPError(
                request.full_url, outcome, "x", {}, __import__("io").BytesIO(b"{}"))
        response = __import__("io").BytesIO(b"{}")
        response.status, response.headers = outcome, {}
        response.__enter__ = lambda: response
        return __import__("contextlib").nullcontext(response)


def test_network_errors_and_gateway_statuses_are_retried(loader, monkeypatch):
    monkeypatch.setattr(loader.time, "sleep", lambda seconds: None)
    request = __import__("urllib.request").request.Request("https://staff-iam.example.org/x")
    opener = FlakyOpener(__import__("urllib.error").error.URLError("connection reset"),
                         TimeoutError("timed out"), 503, 200)
    status, _, _ = loader.fetch(opener, request)
    assert status == 200 and opener.calls == 4


def test_other_statuses_are_returned_and_lasting_failures_raise(loader, monkeypatch):
    monkeypatch.setattr(loader.time, "sleep", lambda seconds: None)
    request = __import__("urllib.request").request.Request("https://staff-iam.example.org/x")
    opener = FlakyOpener(401)
    assert loader.fetch(opener, request)[0] == 401 and opener.calls == 1
    opener = FlakyOpener(*[OSError("unreachable")] * loader.NETWORK_ATTEMPTS)
    with pytest.raises(RuntimeError, match="unreachable"):
        loader.fetch(opener, request)


def test_tls_checks_follow_the_chart_setting(loader, monkeypatch):
    import ssl
    monkeypatch.setenv("INTAKE_SEED_VERIFY_TLS", "false")
    assert loader.tls_context().verify_mode == ssl.CERT_NONE
    monkeypatch.delenv("INTAKE_SEED_VERIFY_TLS")
    assert loader.tls_context().verify_mode == ssl.CERT_REQUIRED


def test_the_task_is_found_on_a_later_page(loader):
    class Pages:
        username = "nina.patel"

        def __init__(self):
            self.pages = []

        def post(self, path, payload):
            self.pages.append(payload["page"])
            if payload["page"] == 1:
                return {"data": {"items": [{"id": f"t{i}", "artifact_id": "other", "stage_order": 2}
                                           for i in range(loader.TASK_PAGE_SIZE)]}}
            return {"data": {"items": [{"id": "mine", "artifact_id": "sub-1", "stage_order": 2}]}}

    approver = Pages()
    assert loader.Loader.open_task(approver, "sub-1", 2)["id"] == "mine" and approver.pages == [1, 2]


def test_a_draft_left_by_a_failed_run_is_completed_not_entered_again(loader):
    first = plan(loader)[0]["stages"][0]["root"]
    registry = FakeRegistry(previous={"502628318720": [("sub-draft", "DRAFT", None, first)]})
    done, submitted, _ = run(loader, registry)
    assert submitted[0] == ("draft", "sub-draft") and done["drafts completed"] == 1


def test_no_intake_starts_once_the_time_budget_is_used(loader):
    registry = FakeRegistry()
    loader.Loader.time_budget, saved = -1, loader.Loader.time_budget
    try:
        done, submitted, _ = run(loader, registry)
    finally:
        loader.Loader.time_budget = saved
    assert submitted == [] and done["intakes left for the next run"] == sum(len(p["stages"]) for p in plan(loader))


def test_one_failing_farmer_does_not_stop_the_others(loader):
    registry = FakeRegistry()
    real = registry.farmer_reference

    def farmer_reference(fayda_id, birth_date, gender, individual_id=None):
        if fayda_id == "502628318720":
            raise RuntimeError("more than one farmer reference")
        return real(fayda_id, birth_date, gender, individual_id)

    registry.farmer_reference = farmer_reference
    done, submitted, _ = run(loader, registry)
    assert done["farmers failed"] == 1 and done["farmers referenced"] == 1 and submitted


def test_a_request_sent_once_is_not_retried(loader):
    import urllib.error
    import urllib.request

    request = urllib.request.Request("https://crop.example.org/awe/submit_task_decision")
    opener = FlakyOpener(urllib.error.URLError("connection reset"), 200)
    with pytest.raises(RuntimeError, match="connection reset"):
        loader.fetch(opener, request, attempts=1)
    assert opener.calls == 1


def test_the_retry_log_leaves_out_the_query(loader, monkeypatch):
    logged = []
    monkeypatch.setattr(loader.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(loader, "log", logged.append)
    request = __import__("urllib.request").request.Request("https://staff-iam.example.org/auth/callback?code=secret")
    loader.fetch(FlakyOpener(503, 200), request)
    assert logged and all("secret" not in line for line in logged)


class StageTwoApprover:
    """Stage 1 was approved by an earlier run; the stage 2 task waits, claimed or open."""

    def __init__(self, stage, claimed, registry, calls):
        self.username, self.stage, self.claimed = f"u{stage}", stage, claimed
        self.registry, self.calls = registry, calls

    def post(self, path, payload, once=False):
        self.calls.append((self.username, path, once))
        if path == "/awe/list_my_tasks":
            wanted = "claimed" if self.claimed else "open"
            if self.stage == 2 and payload["status"] == wanted and self.registry.get("sub-1") != "APPROVED":
                return {"data": {"items": [{"id": "t2", "artifact_id": "sub-1", "stage_order": 2}]}}
            return {"data": {"items": []}}
        if path == "/awe/submit_task_decision":
            self.registry["sub-1"] = "APPROVED"
        return {}


@pytest.mark.parametrize("claimed", [False, True])
def test_approval_resumes_at_the_stage_reached(loader, claimed):
    status, calls = {}, []
    runner = loader.Loader.__new__(loader.Loader)
    runner.registry = types.SimpleNamespace(approval_status=status.get)
    runner.approve_timeout = 5
    runner.approvers = [StageTwoApprover(1, claimed, status, calls), StageTwoApprover(2, claimed, status, calls)]
    runner.approve("sub-1")
    sent = [(user, path) for user, path, once in calls if path != "/awe/list_my_tasks"]
    assert sent == ([] if claimed else [("u2", "/awe/claim_task")]) + [("u2", "/awe/submit_task_decision")]
    assert all(once for _, path, once in calls if path != "/awe/list_my_tasks")


def test_a_lost_decision_is_read_again_not_resent(loader, monkeypatch):
    monkeypatch.setattr(loader.time, "sleep", lambda seconds: None)
    status, calls = {}, []

    class LostAnswer(StageTwoApprover):
        def post(self, path, payload, once=False):
            reply = super().post(path, payload, once)
            if path == "/awe/submit_task_decision":
                raise RuntimeError("POST /awe/submit_task_decision: timed out")
            return reply

    runner = loader.Loader.__new__(loader.Loader)
    runner.registry = types.SimpleNamespace(approval_status=status.get)
    runner.approve_timeout = 5
    runner.approvers = [LostAnswer(1, True, status, calls), LostAnswer(2, True, status, calls)]
    runner.approve("sub-1")
    assert [path for _, path, _ in calls].count("/awe/submit_task_decision") == 1


@pytest.mark.parametrize("status", ["DRAFT", "PENDING"])
def test_an_intake_somebody_else_entered_is_never_completed_or_approved(loader, status):
    draft, approval = ("DRAFT", None) if status == "DRAFT" else ("FINAL", "PENDING")
    registry = FakeRegistry(previous={"502628318720": [("sub-tester", draft, approval, "a-testers-record")]})
    registry.pending = ["sub-tester"]
    done, submitted, _ = run(loader, registry)
    assert ("draft", "sub-tester") not in submitted and submitted[0][0] == "new"
    assert done["intakes resumed at approval"] == 0 and done["drafts completed"] == 0
    assert registry.status.get("sub-tester") is None or registry.status["sub-tester"] != "APPROVED" \
        or ("g2p_register_livestocks", "a-testers-record") not in registry.waited
    assert not any(c for c in registry.decided if c[0] == "sub-tester")


def test_no_request_starts_after_the_hard_limit(loader, monkeypatch):
    monkeypatch.setattr(loader, "HARD_LIMIT", -1)
    opener = FlakyOpener(200)
    with pytest.raises(loader.OutOfTime):
        loader.fetch(opener, __import__("urllib.request").request.Request("https://staff-iam.example.org/x"))
    assert opener.calls == 0


def test_a_try_never_waits_past_the_hard_limit(loader, monkeypatch):
    timeouts = []

    class Recording(FlakyOpener):
        def open(self, request, timeout):
            timeouts.append(timeout)
            return super().open(request, timeout)

    monkeypatch.setattr(loader, "HARD_LIMIT", loader.time.time() - loader.STARTED + 5)
    loader.fetch(Recording(200), __import__("urllib.request").request.Request("https://staff-iam.example.org/x"))
    assert 0 < timeouts[0] <= 5


def test_out_of_time_counts_the_farmer_as_left_not_failed(loader):
    registry = FakeRegistry()

    def farmer_reference(fayda_id, birth_date, gender, individual_id=None):
        raise loader.OutOfTime("POST /x: not sent")

    registry.farmer_reference = farmer_reference
    done, _, _ = run(loader, registry)
    assert done["farmers out of time"] == 2 and done["farmers failed"] == 0


def test_a_refused_decision_waits_before_the_task_is_read_again(loader, monkeypatch):
    slept, status, calls = [], {}, []
    monkeypatch.setattr(loader.time, "sleep", slept.append)

    class RefusedOnce(StageTwoApprover):
        refused = False

        def post(self, path, payload, once=False):
            if path == "/awe/submit_task_decision" and not RefusedOnce.refused:
                RefusedOnce.refused = True
                raise RuntimeError("/awe/submit_task_decision: 409 conflict")
            return super().post(path, payload, once)

    runner = loader.Loader.__new__(loader.Loader)
    runner.registry = types.SimpleNamespace(approval_status=status.get)
    runner.approve_timeout = 5
    runner.approvers = [RefusedOnce(1, True, status, calls), RefusedOnce(2, True, status, calls)]
    runner.approve("sub-1")
    assert slept == [3] and status["sub-1"] == "APPROVED"


def test_the_loaders_own_intake_is_looked_up_by_its_root_record(loader):
    asked = []
    registry = loader.Registry.__new__(loader.Registry)
    registry.rows = lambda sql, params=(): asked.append(params) or []
    registry.stage_intakes("form-1", "502628318720", "root-1")
    assert "root-1" in asked[0]


def test_root_records_are_the_loaders_own_and_stable_across_runs(loader):
    assert [p["stages"][0]["root"] for p in plan(loader)] == [p["stages"][0]["root"] for p in plan(loader)]
    assert len({p["stages"][0]["root"] for p in plan(loader)}) == 2


LOCATION_SECTION = "livestock_livestock_location_section_03"


def test_the_location_section_carries_the_hierarchy_the_form_requires(loader):
    row = plan(loader)[0]["stages"][0]["sections"][LOCATION_SECTION][0]
    root = plan(loader)[0]["stages"][0]["root"]
    assert row["internal_record_id"] == root and row["latitude"] == 14.4 and row["longitude"] == 37.7
    assert row["geo_lowest_level_value_id"] == "ET01010102"
    assert row["geo_code_hierarchy_json"] == {"lowest_level_value_id": "ET01010102", "hierarchy": [
        {"level_id": "l1", "level": "region", "level_mnemonic": "region", "level_value_id": "ET01",
         "level_value_mnemonic": "Tigray"},
        {"level_id": "l2", "level": "zone", "level_mnemonic": "zone", "level_value_id": "ET0101",
         "level_value_mnemonic": "North Western"},
        {"level_id": "l3", "level": "woreda", "level_mnemonic": "woreda", "level_value_id": "ET010101",
         "level_value_mnemonic": "Tahtay Adiyabo"},
        {"level_id": "l4", "level": "kebele", "level_mnemonic": "kebele", "level_value_id": "ET01010102",
         "level_value_mnemonic": "Badme"}]}
    assert (row["region_id"], row["zone_id"], row["woreda_id"], row["kebele_id"]) == (
        "ET01", "ET0101", "ET010101", "ET01010102")


def test_the_location_stops_at_the_lowest_level_the_pack_has(loader):
    people = [PEOPLE[0], {**PEOPLE[1], "geo_pcode": "ET010101"}]
    row = plan(loader, people=people)[1]["stages"][0]["sections"][LOCATION_SECTION][0]
    assert row["geo_lowest_level_value_id"] == "ET010101"
    assert [e["level"] for e in row["geo_code_hierarchy_json"]["hierarchy"]] == ["region", "zone", "woreda"]
    assert "kebele_id" not in row


def test_a_person_without_a_place_keeps_only_the_packs_location(loader):
    people = [PEOPLE[0], {k: v for k, v in PEOPLE[1].items() if k != "geo_pcode"}]
    herds = [HERDS[0], {**HERDS[1], "location": {"latitude": 1.0, "longitude": 2.0}}]
    sections = plan(loader, herds=herds, people=people)[1]["stages"][0]["sections"]
    assert sections[LOCATION_SECTION][0]["latitude"] == 1.0
    assert "geo_lowest_level_value_id" not in sections[LOCATION_SECTION][0]


def test_the_defaults_leave_time_for_every_intake_and_a_wait_over_several_beats(loader):
    assert loader.Loader.time_budget == 660 and loader.HARD_LIMIT == 720 and loader.INGEST_POLL <= 5
    assert loader.Loader.time_budget < loader.HARD_LIMIT <= 900 - 120  # margin to the 15 minute hook wait


class IngestRegistry:
    """Registry.wait_for over a scripted database: the intake's status per look, then the register."""

    def __init__(self, loader, statuses, record_after=None, attempts=2):
        self.statuses, self.record_after, self.looks, self.attempts = list(statuses), record_after, 0, attempts
        self.stuck_query = None
        for name in ("wait_for", "ingest_state", "ingest_failure"):
            setattr(self, name, getattr(loader.Registry, name).__get__(self))

    def status(self):
        return self.statuses[min(self.looks - 1, len(self.statuses) - 1)]

    def rows(self, sql, params=()):
        if "register_ingest_process_attempts" in sql and "WHERE submission_id" in sql:
            self.looks += 1
            return [(self.status(), self.attempts, "boom")]
        if sql.startswith("SELECT register_ingest_process_status FROM"):
            return [(self.status(),)]
        if sql.startswith("SELECT 1 FROM"):
            return [(1,)] if self.record_after is not None and self.looks >= self.record_after else []
        self.stuck_query = (sql, params)
        return [("PENDING", 3, "")]  # the latest unprocessed intake


class Clock:
    """A clock that only the waits move."""

    def __init__(self):
        self.now = 1000.0

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def test_the_ingest_wait_ends_when_the_intake_is_processed_even_under_another_record_id(loader, monkeypatch):
    monkeypatch.setattr(loader, "time", Clock())
    registry = IngestRegistry(loader, ["PENDING", "PENDING", "PROCESSED"])
    registry.wait_for("g2p_register_livestocks", "root", 60, "sub-1")
    assert registry.looks == 3


def test_the_ingest_wait_accepts_the_root_record_too(loader, monkeypatch):
    monkeypatch.setattr(loader, "time", Clock())
    registry = IngestRegistry(loader, ["PENDING"], record_after=2)
    registry.wait_for("g2p_register_livestocks", "root", 60, "sub-1")


def test_a_wait_that_runs_out_raises_pending_with_the_latest_unprocessed_intake(loader, monkeypatch):
    clock = Clock()
    monkeypatch.setattr(loader, "time", clock)
    registry = IngestRegistry(loader, ["PENDING"])
    with pytest.raises(loader.IngestPending, match=r"not ingested within 30s.*PENDING"):
        registry.wait_for("g2p_register_livestocks", "root", 30, "sub-1")
    assert clock.now == 1030.0 and registry.looks >= 10  # polled every few seconds, ended at the timeout
    sql, params = registry.stuck_query
    assert "AND submission_id = %s" in sql and params == ("sub-1",)


@pytest.mark.parametrize("status", ["ERROR", "FAILED", "DEAD", "DEAD_LETTER"])
def test_a_failure_status_that_holds_for_two_polls_ends_the_wait_with_its_error(loader, monkeypatch, status):
    clock = Clock()
    monkeypatch.setattr(loader, "time", clock)
    registry = IngestRegistry(loader, ["PENDING", status, status])
    with pytest.raises(loader.IngestFailed, match=rf"sub-1 failed: status {status}, attempts 2, error 'boom'"):
        registry.wait_for("g2p_register_livestocks", "root", 420, "sub-1")
    assert registry.looks == 3 and clock.now < 1010  # two failure polls in a row, not the whole wait


def test_a_failure_status_seen_once_is_a_retry_in_between_not_the_end(loader, monkeypatch):
    monkeypatch.setattr(loader, "time", Clock())
    registry = IngestRegistry(loader, ["ERROR", "PENDING", "ERROR", "PROCESSED"])
    registry.wait_for("g2p_register_livestocks", "root", 420, "sub-1")  # no raise


def test_a_failure_status_at_the_attempt_limit_is_terminal_at_once(loader, monkeypatch):
    monkeypatch.setattr(loader, "time", Clock())
    registry = IngestRegistry(loader, ["ERROR"], attempts=loader.INGEST_MAX_ATTEMPTS)
    with pytest.raises(loader.IngestFailed, match="attempts 3"):
        registry.wait_for("g2p_register_livestocks", "root", 420, "sub-1")
    assert registry.looks == 1 and loader.INGEST_MAX_ATTEMPTS == 3


def test_a_failed_ingest_counts_as_a_failed_farmer(loader):
    registry = FakeRegistry()

    def wait_for(table, record_id, timeout, submission_id=None):
        raise loader.IngestFailed("ingest of intake x failed: status ERROR")

    registry.wait_for = wait_for
    done, _, _ = run(loader, registry)
    assert done["farmers failed"] == 2 and done["intakes approved, ingest pending"] == 0
    assert done["intakes left for the next run"] == 2


def test_after_the_first_slow_ingest_no_further_farmer_starts(loader):
    registry = FakeRegistry()

    def wait_for(table, record_id, timeout, submission_id=None):
        raise loader.IngestPending("slow")

    registry.wait_for = wait_for
    done, submitted, _ = run(loader, registry)
    assert len(submitted) == 1 and len(registry.looked_up) == 1
    assert done["intakes approved, ingest pending"] == 1 and done["farmers failed"] == 0
    assert done["intakes left for the next run"] == 1  # the second farmer's stage


def test_a_rerun_skips_an_approved_intake_still_pending_but_reports_one_whose_ingest_failed(loader):
    previous = {"502628318720": [("sub-old", "FINAL", "APPROVED", "root-old")]}
    registry = FakeRegistry(previous=previous)
    done, _, _ = run(loader, registry)
    assert done["intakes already approved"] == 1 and done["intakes approved, ingest failed"] == 0
    registry = FakeRegistry(previous=previous)
    registry.failures["sub-old"] = ("status ERROR, attempts 5, error 'boom'", 5)
    done, _, _ = run(loader, registry)
    assert done["intakes approved, ingest failed"] == 1 and done["intakes already approved"] == 0


def test_the_job_start_comes_from_the_environment_or_pid_1_and_ignores_nonsense(loader, monkeypatch):
    now = loader.time.time()
    monkeypatch.setenv("INTAKE_SEED_STARTED_AT", str(now - 120))
    assert abs(loader.job_started() - (now - 120)) < 5
    monkeypatch.setenv("INTAKE_SEED_STARTED_AT", str(now - 99999))
    assert abs(loader.job_started() - now) < 5
    monkeypatch.setenv("INTAKE_SEED_STARTED_AT", "not a number")
    assert abs(loader.job_started() - now) < 5


def test_a_person_waiting_for_the_farmer_reference_is_left_for_the_next_run_not_failed(loader):
    registry = FakeRegistry(references={"721996394985": REFERENCES["721996394985"]})
    done, submitted, _ = run(loader, registry)
    assert done["farmers waiting for their farmer reference"] == 1 and done["farmers failed"] == 0
    assert done["intakes left for the next run"] == 1 and len(submitted) == 1


def test_a_failed_farmer_counts_its_stage_intakes_as_left(loader):
    registry = FakeRegistry()

    def farmer_reference(fayda_id, birth_date, gender, individual_id=None):
        raise RuntimeError("boom")

    registry.farmer_reference = farmer_reference
    done, _, _ = run(loader, registry)
    assert done["farmers failed"] == 2 and done["intakes left for the next run"] == 2


def test_a_failure_in_the_middle_of_an_intake_counts_that_intake_as_left(loader):
    registry = FakeRegistry()
    registry.approval_status = lambda sid: (_ for _ in ()).throw(RuntimeError("database away"))
    done, _, _ = run(loader, registry)
    assert done["farmers failed"] == 2 and done["intakes left for the next run"] == 2
    assert done["intakes submitted"] == 2 and done["intakes approved and in the register"] == 0


def test_a_refused_connection_is_retried_even_for_a_request_sent_once(loader, monkeypatch):
    import urllib.error
    import urllib.request

    monkeypatch.setattr(loader.time, "sleep", lambda seconds: None)
    request = urllib.request.Request("http://api/intake-form-data/save_intake_form_submission")
    refused = urllib.error.URLError(ConnectionRefusedError(111, "Connection refused"))
    opener = FlakyOpener(refused, refused, 200)
    assert loader.fetch(opener, request, attempts=1)[0] == 200 and opener.calls == 3
    opener = FlakyOpener(*[refused] * loader.NETWORK_ATTEMPTS)
    with pytest.raises(RuntimeError, match="Connection refused"):
        loader.fetch(opener, request, attempts=1)
    assert opener.calls == loader.NETWORK_ATTEMPTS


def test_the_loader_waits_for_the_api_to_answer_before_its_first_call(loader, monkeypatch):
    import urllib.error

    slept, logged = [], []
    monkeypatch.setattr(loader.time, "sleep", slept.append)
    monkeypatch.setattr(loader, "log", logged.append)
    opener = FlakyOpener(urllib.error.URLError(ConnectionRefusedError(111, "refused")), 503, 200)
    monkeypatch.setattr(loader.urllib.request, "build_opener", lambda *handlers: opener)
    loader.wait_until_ready("http://api:80/", timeout=60, poll=5)
    assert opener.calls == 3 and slept == [5, 5]
    assert any("answers" in line and "http://api:80/ping" in line for line in logged)


def test_the_readiness_wait_gives_up_after_its_timeout_and_lets_the_first_call_report(loader, monkeypatch):
    import urllib.error

    monkeypatch.setattr(loader.time, "sleep", lambda seconds: None)
    opener = FlakyOpener(*[urllib.error.URLError(ConnectionRefusedError(111, "refused"))] * 50)
    monkeypatch.setattr(loader.urllib.request, "build_opener", lambda *handlers: opener)
    ticks = itertools.count(0, 100)
    monkeypatch.setattr(loader.time, "time", lambda: loader.STARTED + next(ticks) / 100)
    loader.wait_until_ready("http://api", timeout=3, poll=1)
    assert 1 <= opener.calls < 50


def test_main_waits_for_the_api_before_signing_in():
    source = (SEED / "load_sample_data.py").read_text(encoding="utf-8")
    main = source[source.index("def main()"):]
    assert main.index("wait_until_ready(api)") < main.index("session(env(")


def test_a_rerun_does_not_count_an_approved_intake_that_is_not_ingested_as_already_approved(loader):
    previous = {"502628318720": [("sub-old", "FINAL", "APPROVED", "root-old")]}
    registry = FakeRegistry(previous=previous)
    registry.unprocessed.add("sub-old")
    done, submitted, _ = run(loader, registry)
    assert done["intakes already approved"] == 0 and done["intakes approved, ingest pending"] == 1
    assert done["farmers failed"] == 0 and submitted == []  # the second farmer waits for the next run
    assert done["intakes left for the next run"] == 1 and len(registry.looked_up) == 1


def test_a_country_level_place_gives_no_location_section_and_is_logged(loader, monkeypatch):
    logged = []
    monkeypatch.setattr(loader, "log", logged.append)
    assert loader.location_section([PLACES["ET"]], "root", {"latitude": 1.0}) is None
    people = [PEOPLE[0], {**PEOPLE[1], "geo_pcode": "ET"}]
    sections = plan(loader, people=people)[1]["stages"][0]["sections"]
    assert LOCATION_SECTION not in sections and any("no Location section" in line for line in logged)
    # With coordinates in the pack, the coordinates are kept without a hierarchy.
    herds = [HERDS[0], {**HERDS[1], "location": {"latitude": 1.0, "longitude": 2.0}}]
    row = plan(loader, herds=herds, people=people)[1]["stages"][0]["sections"][LOCATION_SECTION][0]
    root = plan(loader, herds=herds, people=people)[1]["stages"][0]["root"]
    assert row == {"internal_record_id": root, "latitude": 1.0, "longitude": 2.0}
    assert any("pack's coordinates only" in line for line in logged)
