#!/usr/bin/env python3
"""Load the Livestock Registry's sample data (db-seed, LOAD_SAMPLE_DATA=true).

The sample farmers are the Farmer Registry's sample people (the ETH-OAN pack in
openg2p-data). Seeding never asks the Farmer Registry for them, which need not
be running: each one is written straight into this registry's own farmer
register, as an approved farmer reference carrying the pack's sample Farmer ID
(samples/farmer_ids.json). A sample person this registry already references
keeps that reference and its Farmer ID; a reference whose farmer copy is gone
gets the copy back.

Their livestock is entered the way an officer enters it, and approved the way
every register change is approved:

- for each person in samples/livestock.json, one Livestock intake (survey
  personnel, location, animals and their health, vaccination, vital and
  breeding events), saved section by section through the staff API;
- the intake is linked to the seeded farmer reference before it is finalized,
  so finalizing does not look the farmer up in the Farmer Registry;
- the approval request's stage 1 is approved as INTAKE_SEED_APPROVER_1 and its
  stage 2 as INTAKE_SEED_APPROVER_2, through the staff API's AWE proxy;
- the registry's workers ingest the approved intake into the register.

Every value comes from the pack; the loader only copies it into the form.

Staff accounts sign in as in the staff portal (staff IAM, then the Keycloak
login form, then IAM's callback), with the sample users' password the chart
passes (global.aweApproverUserPassword). The loader never uses the password
grant and never changes Keycloak.

The staff IAM address is STAFF_IAM_URL when set. The platform's db-seed job
(registry chart 1.2.2-rc.614) passes the staff API, the Keycloak token URL and
the sample users, but no IAM address, so without it the loader takes IAM's
public host from the Keycloak host the job does pass: keycloak.<domain> gives
staff-iam.<domain>, the platform's own host names. It must be the public host:
Keycloak returns the sign-in to IAM's public callback, and IAM's cookies are
issued for that domain.

Idempotent: a person whose Livestock intake is already approved is skipped; a
finalized intake still waiting for approval is approved rather than entered
again. A draft intake a failed run left behind (it is linked to
the farmer reference as soon as it exists) is completed rather than entered
again: saving a section replaces that section's rows.

A sample farmer whose intake fails (after the network retries) is logged and
counted, and the others still load; sample data never fails the upgrade it
rides on. The next seed run picks the farmer up again.

Within the seed job's time: once INTAKE_SEED_TIME_BUDGET seconds (default 480)
have passed the loader starts no further intake and ends successfully; the
next upgrade's seed continues where it stopped. INTAKE_SEED_APPROVE_TIMEOUT and
INTAKE_SEED_INGEST_TIMEOUT (default 180 s each) bound the intake in progress.

Network: requests cross the public ingress (staff IAM, Keycloak) and the
staff API; a connection error, a timeout or a gateway status (502, 503, 504)
is retried with backoff. INTAKE_SEED_VERIFY_TLS=false (what the chart sets)
skips certificate checks. The chart's INTAKE_SEED_MAX_HOUSEHOLDS and KEYCLOAK_*
settings are not used: the pack decides what is loaded and Keycloak is never
called directly.
"""

from __future__ import annotations

import html
import http.cookiejar
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
from psycopg2.extras import Json

INTAKE_ARTIFACT = "registry.intake_form"
TRANSIENT_HTTP = (502, 503, 504)  # the gateway's answer when the service behind it is away
NETWORK_ATTEMPTS = 5
TASK_PAGE_SIZE, TASK_PAGES = 100, 20
PACK = os.environ.get("SAMPLE_PACK", "ETH-OAN")
OPENG2P_DATA_DIR = Path(os.environ.get("OPENG2P_DATA_DIR", "/openg2p-data"))
SOURCE_SYSTEM = os.environ.get("FARMER_REFERENCE_SOURCE_SYSTEM", "farmer-registry")
DIAL_CODE = "+251"
LOOKUP = "livestock_farmer_lookup"
# The form, its survey personnel section, and its list sections with the pack key
# that fills them; the first list (animals) must have rows.
STAGES = (
    ("Livestock Intake", "livestock_survey_personnel_section_02",
     (("livestock_animal_details_section_01", "animals"),
      ("livestock_health_event_details_section_01", "health_events"),
      ("livestock_vaccination_details_section_01", "vaccinations"),
      ("livestock_vital_event_details_section_01", "vital_events"),
      ("livestock_breeding_details_section_01", "breeding"))),
)
LOCATION = "livestock_livestock_location_section_03"


def log(message: str) -> None:
    print(f"[load-sample-data] {message}", flush=True)


def words(*parts) -> str:
    return " ".join(str(p) for p in parts if p not in (None, ""))


def local_phone(e164: str | None) -> str | None:
    """+251941923320 -> 0941923320, the way an officer types it."""
    if not e164:
        return None
    return "0" + e164[len(DIAL_CODE):] if e164.startswith(DIAL_CODE) else e164.lstrip("+")


class Pack:
    """The ETH-OAN pack's sample files in the openg2p-data checkout."""

    def __init__(self, root: Path):
        self.root = root

    def read(self, name: str):
        return json.loads((self.root / "samples" / name).read_text(encoding="utf-8"))

    def places(self) -> dict[str, dict]:
        return {v["level_value_id"]: v for v in json.loads((self.root / "values.json").read_text(encoding="utf-8"))}


def place_chain(places: dict[str, dict], pcode: str) -> list[dict]:
    chain, code = [], pcode
    while code:
        unit = places.get(code)
        if unit is None:
            raise RuntimeError(f"{pcode} is not a unit of the pack's geography")
        chain.insert(0, unit)
        code = unit.get("parent_level_value_id")
    return chain


def farmer_copy(person: dict, farm: dict, farmer_id: str, places: dict[str, dict]) -> dict:
    """The person as this registry's farmer register holds a Farmer: the reference profile fields."""
    names = (person.get("given_name"), person.get("fathers_name"),
             (farm.get("farmer") or {}).get("grandfathers_name"))
    if not all(names):
        raise RuntimeError(f"{person['individual_id']} needs a given, father's and grandfather's name")
    name = words(*names)
    copy = {
        "farmer_id": farmer_id, "fayda_fin": person["national_id"], "farmer_name": name,
        "first_name": names[0], "middle_name": names[1], "last_name": names[2],
        "gender": person.get("gender"), "date_of_birth": person.get("birth_date"),
        "mobile_number": local_phone(person.get("phone")), "country_code": "ET",
        "latitude": person.get("latitude"), "longitude": person.get("longitude"),
    }
    pcode = person.get("geo_pcode")
    if pcode:
        chain = place_chain(places, pcode)
        copy["geo_lowest_level_value_id"] = pcode
        copy["geo_code_hierarchy_json"] = {"lowest_level_value_id": pcode, "hierarchy": [
            {"level_id": u["level_id"], "level_value_id": u["level_value_id"],
             "level_value_mnemonic": u["level_value_mnemonic"]} for u in chain]}
        for unit, level in zip(chain[1:], ("region", "zone", "woreda", "kebele")):
            copy[f"{level}_id"], copy[f"{level}_name"] = unit["level_value_id"], unit["level_value_mnemonic"]
    return farmer_with_id(copy, farmer_id)


def farmer_with_id(copy: dict, farmer_id: str) -> dict:
    """The farmer copy under a Farmer ID, with the record name and search text the ORM would derive."""
    return {**copy, "farmer_id": farmer_id, "record_name": words(copy["farmer_name"], farmer_id),
            "search_text": words(farmer_id, copy["fayda_fin"], copy["farmer_name"], copy.get("mobile_number"))}


def plan(people: list[dict], farms: dict, farmer_ids: dict, herds: list[dict], places: dict,
         new_id=lambda: str(uuid.uuid4())) -> list[dict]:
    """One entry per person with livestock samples: their farmer copy and their Livestock intake."""
    by_id = {p["individual_id"]: p for p in people}
    planned = []
    for sample in herds:
        who = sample["individual_id"]
        person = by_id.get(who)
        if person is None:
            raise RuntimeError(f"livestock.json names {who}, who is not a sample person")
        if who not in farmer_ids:
            raise RuntimeError(f"farmer_ids.json has no sample Farmer ID for {who}")
        if not person.get("national_id"):
            raise RuntimeError(f"{who} has no Fayda ID")
        stages = []
        for form, personnel_section, lists in STAGES:
            if not sample.get(lists[0][1]):
                raise RuntimeError(f"{who} has no animals; a Livestock record needs at least one")
            root = new_id()
            sections = {
                LOOKUP: [{"internal_record_id": root, "farmer_id": farmer_ids[who],
                          "fayda_id": person["national_id"]}],
                personnel_section: [{"internal_record_id": root, **(sample.get("survey_personnel") or {})}],
            }
            if sample.get("location"):
                sections[LOCATION] = [{"internal_record_id": root, **sample["location"]}]
            for section, key in lists:
                rows = [{"internal_record_id": new_id(), "link_internal_record_id": root, **line}
                        for line in sample.get(key) or []]
                if rows:
                    sections[section] = rows
            stages.append({"form": form, "root": root, "sections": sections})
        planned.append({
            "individual_id": who, "foundational_id": person["national_id"], "farmer_id": farmer_ids[who],
            "farmer": farmer_copy(person, farms.get(who) or {}, farmer_ids[who], places), "stages": stages,
        })
    return planned


def tls_context() -> ssl.SSLContext:
    """Certificates are checked unless INTAKE_SEED_VERIFY_TLS is false."""
    context = ssl.create_default_context()
    if os.environ.get("INTAKE_SEED_VERIFY_TLS", "true").strip().lower() == "false":
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    return context


def fetch(opener, request, timeout: int = 60) -> tuple[int, object, bytes]:
    """Status, headers and body; network errors and gateway statuses are retried with backoff."""
    for attempt in range(1, NETWORK_ATTEMPTS + 1):
        try:
            with opener.open(request, timeout=timeout) as response:
                status, headers, body = response.status, response.headers, response.read()
        except urllib.error.HTTPError as exc:
            status, headers, body = exc.code, exc.headers, exc.read()
        except (urllib.error.URLError, OSError) as exc:
            if attempt == NETWORK_ATTEMPTS:
                raise RuntimeError(f"{request.get_method()} {request.full_url}: {exc}") from exc
            status, headers, body = None, None, str(exc)
        if status is not None and (status not in TRANSIENT_HTTP or attempt == NETWORK_ATTEMPTS):
            return status, headers, body
        wait = 2 ** attempt
        log(f"{request.get_method()} {request.full_url}: {status or body}; again in {wait}s")
        time.sleep(wait)
    raise AssertionError("unreachable")


class StaffSession:
    """One staff user signed in like the staff portal: IAM, the Keycloak login form, IAM's callback."""

    def __init__(self, iam_url: str, api_url: str, username: str, password: str):
        self.iam_url, self.api_url = iam_url.rstrip("/"), api_url.rstrip("/")
        self.username, self._password = username, password
        self._token = None
        self._api = urllib.request.build_opener(urllib.request.HTTPSHandler(context=tls_context()))
        self.sign_in()

    @staticmethod
    def _open(opener, request) -> tuple[int, object, bytes]:
        """Status, headers (looked up case-insensitively) and body, without following redirects."""
        return fetch(opener, request)

    def sign_in(self) -> None:
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None

        jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), NoRedirect,
                                             urllib.request.HTTPSHandler(context=tls_context()))
        status, _, body = self._open(opener, urllib.request.Request(
            f"{self.iam_url}/auth/start_authentication_transaction?id=1&redirect_uri=/en", data=b"", method="POST"))
        if status != 200:
            raise RuntimeError(f"staff IAM did not start a sign-in for {self.username} ({status})")
        status, _, body = self._open(opener, urllib.request.Request(json.loads(body)["redirectUrl"] + "&prompt=login"))
        form = re.search(r'<form[^>]+id="kc-form-login"[^>]+action="([^"]+)"', body.decode("utf-8", "replace"))
        if status != 200 or not form:
            raise RuntimeError(f"no Keycloak login form for {self.username} ({status})")
        login = urllib.parse.urlencode({"username": self.username, "password": self._password, "credentialId": ""})
        status, headers, body = self._open(opener, urllib.request.Request(
            html.unescape(form.group(1)), data=login.encode(), method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"}))
        callback = headers.get("Location") or ""
        if not callback.startswith(f"{self.iam_url}/auth/callback"):
            said = " ".join(re.findall(r'kc-feedback-text[^>]*>([^<]+)', body.decode("utf-8", "replace")))
            raise RuntimeError(f"Keycloak refused the sign-in of {self.username} ({status}): {said.strip()[:200]} "
                               "(INTAKE_SEED_PASSWORD is the chart value global.aweApproverUserPassword; "
                               "it must be the sample users' Keycloak password)")
        status, _, _ = self._open(opener, urllib.request.Request(callback))
        token = next((c.value for c in jar if c.name == "X-Access-Token"), None)
        if status not in (302, 303, 307) or not token:
            raise RuntimeError(f"staff IAM issued no session for {self.username} ({status})")
        self._token = token
        log(f"signed in as {self.username}")

    def _send(self, path: str, data: bytes, content_type: str) -> tuple[int, dict]:
        for attempt in (1, 2):
            csrf = uuid.uuid4().hex
            request = urllib.request.Request(f"{self.api_url}{path}", data=data, method="POST", headers={
                "Authorization": f"Bearer {self._token}", "X-CSRF-Token": csrf, "Cookie": f"X-CSRF-Token={csrf}",
                "Content-Type": content_type})
            status, _, body = fetch(self._api, request, 120)
            try:
                reply = json.loads(body or b"{}")
            except ValueError:
                reply = {}
            code = str((reply.get("response_header") or {}).get("response_error_code") or "")
            if attempt == 1 and (status == 401 or code.endswith("401")):
                self.sign_in()  # the session ended during a long run
                continue
            return status, reply
        return status, reply

    def post(self, path: str, payload: dict) -> dict:
        envelope = {
            "request_header": {"sender_app_mnemonic": "livestock-db-seed", "sender_app_url": "http://db-seed",
                               "request_id": str(uuid.uuid4()),
                               "request_timestamp": datetime.now(timezone.utc).isoformat()},
            "request_body": {"request_payload": payload, "pagination_request": {"current_page": 1, "page_size": 100}},
        }
        status, reply = self._send(path, json.dumps(envelope).encode(), "application/json")
        header = reply.get("response_header") or {}
        if status != 200 or header.get("response_status") != "SUCCESS":
            raise RuntimeError(f"{path} as {self.username}: {status} {header.get('response_error_code')} "
                               f"{header.get('response_error_message')}")
        return (reply.get("response_body") or {}).get("response_payload") or {}


class Registry:
    """The registry database: form metadata, the farmer references this loader seeds, intake progress."""

    def __init__(self):
        self.conn = psycopg2.connect(host=env("PGHOST"), port=os.environ.get("PGPORT", "5432"),
                                     dbname=env("PGDATABASE"), user=env("PGUSER"), password=env("PGPASSWORD"))
        self.conn.autocommit = True

    def rows(self, sql: str, params=()) -> list[tuple]:
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    def forms(self) -> dict[str, tuple[str, str, dict[str, str]]]:
        """Each stage form's id, its register, and the register of each of its sections."""
        found = self.rows(
            "SELECT f.form_mnemonic, f.form_id, f.register_id, s.section_id, s.section_register_id"
            " FROM g2p_intake_form_definitions f"
            " JOIN g2p_intake_form_ui_tabs t ON t.form_id = f.form_id"
            " JOIN g2p_intake_form_ui_tab_sections ts ON ts.tab_id = t.tab_id"
            " JOIN g2p_register_sections s ON s.section_id = ts.section_id"
            " WHERE f.form_mnemonic = ANY(%s)", ([form for form, _, _ in STAGES],))
        forms: dict[str, tuple[str, str, dict[str, str]]] = {}
        for mnemonic, form_id, register_id, section, register in found:
            forms.setdefault(mnemonic, (str(form_id), str(register_id), {}))[2][section] = str(register)
        for form, season_section, lists in STAGES:
            if form not in forms:
                raise RuntimeError(f"form {form} is not in the registry metadata")
            wanted = [LOOKUP, season_section, *(section for section, _ in lists)]
            missing = [s for s in wanted if s not in forms[form][2]]
            if missing:
                raise RuntimeError(f"form {form} has no section {', '.join(missing)}")
        return forms

    def ensure_farmer(self, farmer: dict, created_by: str, approved_by: str, source_record_id: str) -> dict:
        """The approved farmer reference for this Fayda ID, written straight in when there is none."""
        self.conn.autocommit = False
        try:
            with self.conn.cursor() as cur:
                reference = self._ensure_farmer(cur, farmer, created_by, approved_by, source_record_id)
            self.conn.commit()
            return reference
        except Exception:
            self.conn.rollback()
            raise
        finally:
            self.conn.autocommit = True

    @staticmethod
    def _ensure_farmer(cur, farmer: dict, created_by: str, approved_by: str, source_record_id: str) -> dict:
        fin = farmer["fayda_fin"]
        cur.execute("SELECT reference_id, farmer_id, local_farmer_id, state FROM coss_farmer_references"
                    " WHERE source_system = %s AND uid = %s FOR UPDATE", (SOURCE_SYSTEM, fin))
        found = cur.fetchone()
        if found:
            reference_id, farmer_id, local_id, state = found
            if state != "APPROVED":
                raise RuntimeError(f"the farmer reference for {fin} is {state}, not APPROVED")
            cur.execute("SELECT 1 FROM g2p_register_farmers WHERE internal_record_id = %s", (local_id,))
            if cur.fetchone():
                return {"reference_id": reference_id, "farmer_id": farmer_id, "local_farmer_id": local_id,
                        "seeded": "referenced"}
            # The reference outlived its farmer copy: write the copy back under the reference's ids.
            Registry._insert_farmer(cur, farmer_with_id(farmer, farmer_id), str(local_id), created_by, approved_by)
            return {"reference_id": reference_id, "farmer_id": farmer_id, "local_farmer_id": local_id,
                    "seeded": "restored"}
        cur.execute("SELECT internal_record_id, farmer_id, record_status, last_approved_at"
                    " FROM g2p_register_farmers WHERE fayda_fin = %s OR farmer_id = %s", (fin, farmer["farmer_id"]))
        local = cur.fetchall()
        if len(local) > 1 or (local and (local[0][1] != farmer["farmer_id"] or local[0][2] != "ACTIVE"
                                         or not local[0][3])):
            raise RuntimeError(f"this registry already holds another farmer for {fin} or {farmer['farmer_id']}; "
                               "leaving it alone")
        local_id = str(local[0][0]) if local else str(uuid.uuid4())
        if not local:
            Registry._insert_farmer(cur, farmer, local_id, created_by, approved_by)
        reference_id = str(uuid.uuid4())
        cur.execute("INSERT INTO coss_farmer_references (reference_id, source_system, source_record_id, farmer_id,"
                    " uid, local_farmer_id, applied_version, state) VALUES (%s, %s, %s, %s, %s, %s, 0, 'APPROVED')",
                    (reference_id, SOURCE_SYSTEM, source_record_id, farmer["farmer_id"], fin, local_id))
        return {"reference_id": reference_id, "farmer_id": farmer["farmer_id"], "local_farmer_id": local_id,
                "seeded": "seeded"}

    @staticmethod
    def _insert_farmer(cur, farmer: dict, local_id: str, created_by: str, approved_by: str) -> None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        columns = {"internal_record_id": local_id, "created_by": created_by, "created_at": now,
                   "last_approved_at": now, "last_approved_by": approved_by, "record_status": "ACTIVE", **farmer}
        if columns.get("geo_code_hierarchy_json"):
            columns["geo_code_hierarchy_json"] = Json(columns["geo_code_hierarchy_json"])
        cur.execute(f'INSERT INTO "public"."g2p_register_farmers" ({", ".join(columns)})'
                    f" VALUES ({', '.join(['%s'] * len(columns))})", list(columns.values()))

    def link(self, submission_id: str, reference_id: str) -> None:
        """Tie a draft intake to its approved farmer reference, so finalizing needs no Farmer lookup."""
        self.rows("INSERT INTO coss_farmer_submission_dependencies (submission_id, reference_id)"
                  " VALUES (%s, %s) ON CONFLICT (submission_id) DO NOTHING RETURNING 1", (submission_id, reference_id))

    def stage_intakes(self, form_id: str, fin: str) -> list[tuple[str, str, str, str]]:
        """This person's intakes on the form: (submission, draft, approval, root record)."""
        return [(str(sid), draft, approval, str(rid)) for sid, draft, approval, rid in self.rows(
            "SELECT s.submission_id, s.draft_status, s.approval_status, l.internal_record_id"
            " FROM g2p_intake_form_submissions s JOIN g2p_intake_form_livestocks l ON l.submission_id = s.submission_id"
            " WHERE s.form_id = %s AND l.fayda_fin = %s", (form_id, fin))]

    def approval_status(self, submission_id: str) -> str | None:
        found = self.rows("SELECT approval_status FROM g2p_intake_form_submissions WHERE submission_id = %s",
                          (submission_id,))
        return found[0][0] if found else None

    def wait_for(self, table: str, record_id: str, timeout: int) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.rows(f'SELECT 1 FROM "public"."{table}" WHERE internal_record_id = %s', (record_id,)):
                return
            time.sleep(3)
        stuck = self.rows(
            "SELECT register_ingest_process_status, register_ingest_process_attempts,"
            " left(coalesce(register_ingest_process_last_error_code, ''), 300) FROM g2p_intake_form_submissions"
            " WHERE approval_status = 'APPROVED' AND register_ingest_process_status <> 'PROCESSED'"
            " ORDER BY approved_at DESC LIMIT 1")
        raise RuntimeError(f"{table} {record_id} was not ingested within {timeout}s"
                           + (f" (latest unprocessed intake: {stuck[0]})" if stuck else ""))


class Loader:
    time_budget = 480  # seconds; INTAKE_SEED_TIME_BUDGET overrides

    def __init__(self, registry: Registry, submitter: StaffSession, approvers: list[StaffSession],
                 approve_timeout: int, ingest_timeout: int):
        self.registry, self.submitter, self.approvers = registry, submitter, approvers
        self.time_budget = int(os.environ.get("INTAKE_SEED_TIME_BUDGET", "").strip() or self.time_budget)
        self.approve_timeout, self.ingest_timeout = approve_timeout, ingest_timeout
        self.forms = registry.forms()

    def submit(self, stage: dict, reference_id: str, submission_id: str | None = None) -> str:
        """Save every section (into the given draft, or a new one), then finalize.

        The submission is linked to the farmer reference as soon as it exists, so a draft a failed run
        leaves behind is found and completed by the next run; saving a section replaces its rows.
        """
        form_id, register_id, registers = self.forms[stage["form"]]
        if submission_id:
            self.registry.link(submission_id, reference_id)
        for section, rows in stage["sections"].items():
            saved = self.submitter.post("/intake-form-data/save_intake_form_submission", {
                "submission_id": submission_id, "section_id": section, "section_payload": rows,
                "section_register_id": registers[section], "form_id": form_id, "register_id": register_id,
                "created_by": self.submitter.username, "documents": [],
            })
            if not submission_id:
                submission_id = saved.get("submission_id")
                if not submission_id:
                    raise RuntimeError(f"saving {section} on {stage['form']} returned no submission")
                self.registry.link(submission_id, reference_id)
        self.submitter.post("/intake-form-data/finalize_intake_form_submission", {
            "submission_id": submission_id, "register_id": register_id, "form_id": form_id})
        return submission_id

    def approve(self, submission_id: str) -> None:
        """Stage 1 as the first approver, then stage 2 as the second, each once its task opens."""
        deadline = time.time() + self.approve_timeout
        for stage, approver in enumerate(self.approvers, 1):
            while True:
                if self.registry.approval_status(submission_id) == "APPROVED":
                    return
                task = self.open_task(approver, submission_id, stage)
                if task:
                    break
                if time.time() > deadline:
                    raise RuntimeError(f"no stage {stage} task for {approver.username} on intake {submission_id} "
                                       f"within {self.approve_timeout}s")
                time.sleep(3)
            approver.post("/awe/claim_task", {"task_id": task["id"]})
            approver.post("/awe/submit_task_decision", {
                "task_id": task["id"], "action": "approve", "comment": "Sample data (db-seed)",
                "artifact_id": submission_id, "artifact_type": INTAKE_ARTIFACT, "current_stage": stage})
            log(f"      stage {stage} approved as {approver.username}")
        while self.registry.approval_status(submission_id) != "APPROVED":
            if time.time() > deadline:
                raise RuntimeError(f"intake {submission_id} is not approved after both stages")
            time.sleep(3)

    @staticmethod
    def open_task(approver: StaffSession, submission_id: str, stage: int) -> dict | None:
        """The approver's open task for this intake and stage, looked up page by page."""
        for page in range(1, TASK_PAGES + 1):
            tasks = approver.post("/awe/list_my_tasks", {"status": "open", "artifact_type": INTAKE_ARTIFACT,
                                                         "page": page, "page_size": TASK_PAGE_SIZE})
            items = (tasks.get("data") or {}).get("items") or []
            task = next((t for t in items
                         if t.get("artifact_id") == submission_id and int(t.get("stage_order") or 0) == stage), None)
            if task or len(items) < TASK_PAGE_SIZE:
                return task
        return None

    def run(self, planned: list[dict]) -> dict:
        done = {"farmers seeded": 0, "farmers restored": 0, "farmers referenced": 0, "intakes approved": 0,
                "resumed": 0, "drafts completed": 0, "skipped": 0, "left for the next run": 0, "failed": 0}
        stop_at = time.time() + self.time_budget
        approved_by = self.approvers[-1].username
        for person in planned:
            try:
                who = f"{person['individual_id']} {person['farmer']['farmer_name']}"
                reference = self.registry.ensure_farmer(person["farmer"], self.submitter.username, approved_by,
                                                        person["individual_id"])
                done[f"farmers {reference['seeded']}"] += 1
                log(f"  {who}: farmer {reference['farmer_id']} {reference['seeded']}")
                for stage in person["stages"]:
                    if time.time() > stop_at:
                        done["left for the next run"] += 1
                        continue
                    form_id = self.forms[stage["form"]][0]
                    stage = self._with_farmer_id(stage, reference["farmer_id"])
                    previous = self.registry.stage_intakes(form_id, person["foundational_id"])
                    if any(approval == "APPROVED" for _, _, approval, _ in previous):
                        done["skipped"] += 1
                        log(f"    {stage['form']}: already approved")
                        continue
                    waiting = next(((sid, rid) for sid, draft, approval, rid in previous
                                    if draft == "FINAL" and approval == "PENDING"), None)
                    draft = next((sid for sid, status, _, _ in previous if status == "DRAFT"), None)
                    if waiting:
                        submission_id, root = waiting
                        log(f"    {stage['form']}: intake {submission_id} waits for approval; approving it")
                        done["resumed"] += 1
                    elif draft:
                        submission_id, root = self.submit(stage, reference["reference_id"], draft), stage["root"]
                        log(f"    {stage['form']}: draft intake {submission_id} completed and submitted")
                        done["drafts completed"] += 1
                    else:
                        submission_id, root = self.submit(stage, reference["reference_id"]), stage["root"]
                        log(f"    {stage['form']}: intake {submission_id} submitted")
                        done["intakes approved"] += 1
                    self.approve(submission_id)
                    self.registry.wait_for("g2p_register_livestocks", root, self.ingest_timeout)
                    log(f"    {stage['form']}: in the register")
            except RuntimeError as exc:
                done["failed"] += 1
                log(f"  {person['individual_id']}: FAILED, left for the next run: {exc}")
        if done["left for the next run"]:
            log(f"time budget of {self.time_budget}s used: {done['left for the next run']} stage intakes are left "
                "for the next seed run")
        return done

    @staticmethod
    def _with_farmer_id(stage: dict, farmer_id: str) -> dict:
        """The stage with the Farmer ID of the reference used (an existing one keeps its own)."""
        lookup = [{**stage["sections"][LOOKUP][0], "farmer_id": farmer_id}]
        return {**stage, "sections": {**stage["sections"], LOOKUP: lookup}}


def env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, "").strip() or default
    if not value:
        raise RuntimeError(f"{name} is not set")
    return value


def staff_iam_url() -> str:
    """STAFF_IAM_URL, or IAM's public host next to Keycloak's (keycloak.<domain> -> staff-iam.<domain>)."""
    if os.environ.get("STAFF_IAM_URL", "").strip():
        return env("STAFF_IAM_URL")
    token_url = urllib.parse.urlsplit(env("STAFF_TOKEN_URL"))
    label, _, domain = token_url.netloc.partition(".")
    if label != "keycloak" or not domain:
        raise RuntimeError(f"STAFF_IAM_URL is not set and the Keycloak host {token_url.netloc} "
                           "is not keycloak.<domain>")
    return f"{token_url.scheme}://staff-iam.{domain}"


def main() -> None:
    pack = Pack(OPENG2P_DATA_DIR / "packs" / PACK)
    herds = pack.read("livestock.json")
    if not herds:
        log(f"the {PACK} pack has no livestock samples: nothing to load.")
        return
    farmer_ids = {f["individual_id"]: f["farmer_id"] for f in pack.read("farmer_ids.json")}
    farms = {f["individual_id"]: f for f in pack.read("farms.json")}
    planned = plan(pack.read("individuals.json"), farms, farmer_ids, herds, pack.places())
    animals = sum(len(s["sections"].get(STAGES[0][2][0][0], [])) for p in planned for s in p["stages"])
    log(f"{len(planned)} sample farmers with livestock, {animals} animal rows, from {pack.root}")

    iam, api, password = staff_iam_url(), env("STAFF_API_URL"), env("INTAKE_SEED_PASSWORD")
    log(f"staff IAM {iam}")
    sessions: dict[str, StaffSession] = {}

    def session(user: str) -> StaffSession:
        if user not in sessions:
            sessions[user] = StaffSession(iam, api, user, password)
        return sessions[user]

    registry = Registry()
    try:
        loader = Loader(
            registry, session(env("INTAKE_SEED_SUBMIT_USER", "alex.carter")),
            [session(env("INTAKE_SEED_APPROVER_1", "alex.carter")),
             session(env("INTAKE_SEED_APPROVER_2", "nina.patel"))],
            int(env("INTAKE_SEED_APPROVE_TIMEOUT", "180")), int(env("INTAKE_SEED_INGEST_TIMEOUT", "180")))
        done = loader.run(planned)
    finally:
        registry.conn.close()
    log("Done: " + ", ".join(f"{count} {what}" for what, count in done.items()) + ".")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[load-sample-data] FAILED: {exc}", file=sys.stderr)
        raise
