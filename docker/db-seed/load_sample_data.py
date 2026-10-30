#!/usr/bin/env python3
"""Load the Livestock Registry's sample data (db-seed, LOAD_SAMPLE_DATA=true).

The sample farmers are the Farmer Registry's sample people (the ETH-OAN pack in
openg2p-data). This loader never creates a Farmer or a Farmer reference and
never invents a Farmer ID: the Farmer Registry generates every Farmer ID, and
its outgestion events deliver each approved Farmer to this registry as a Farmer
reference change request, approved here by the registry's own approvers. The
loader finds a sample person's Farmer reference by the person's Fayda number
(then checks birth date and gender), takes the real Farmer ID from it, and
enters the person's records with it. The database is only read; every write
goes through the staff API.

A person whose Farmer reference is missing or not yet approved is not a
failure: the person is counted as waiting for the Farmer reference, logged,
and left for the next run.

Their livestock is entered the way an officer enters it, and approved the way
every register change is approved:

- for each person in samples/livestock.json, one Livestock intake (survey
  personnel, location, animals and their health, vaccination, vital and
  breeding events), saved section by section through the staff API;
- finalizing is the platform's own step: it looks the declared Farmer ID and Fayda
  number up and links the approved Farmer reference;
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
again. A draft intake a failed run left behind is completed rather than entered
again: saving a section replaces that section's rows.

A sample farmer whose intake fails (after the network retries) is logged and
counted, and the others still load. A failure before any farmer (a setting,
the database, a sign-in) is logged and the loader ends without sample data:
sample data never fails the upgrade it rides on. The next seed run tries again.

Only the loader's own intakes are ever resumed: the root record of each intake
it enters has an id only the loader makes (uuid5 of the sample person, the form
and the year), and the platform keeps that id from the first saved section on.
An intake somebody else entered for a sample person (a tester's draft or
pending intake) is never completed or approved by the loader.

Approvals are restart-safe: the loader looks up the intake's open or claimed
task at whichever stage it has reached, so a stage approved by an earlier run
is not looked for again; a claim or a decision is sent once and, when its
answer is lost, the task is read again instead of resending it.

Within the seed job's time (the deploy waits 15 minutes for the hook): the
clock starts with the loader. After INTAKE_SEED_TIME_BUDGET seconds (default
660) no further intake starts, and after INTAKE_SEED_HARD_LIMIT (default 720)
no request starts and no wait goes on (each try's timeout is cut to the time
left); what is left is counted and the next upgrade's seed continues it, so
the loader ends within 12 minutes, leaving 3 minutes of the hook wait for
the Job's end. The clock starts at the container's start (see job_started),
not at this script's import. INTAKE_SEED_APPROVE_TIMEOUT (default 180 s)
and INTAKE_SEED_INGEST_TIMEOUT (default 420 s) bound the waits of one intake.

The ingest wait watches the approved intake's own ingest status
(register_ingest_process_status = PROCESSED), as the register's record may carry
an id the ingest chose, not the loader's root id (the worker beats approve,
ingest and allocate ids in turn, 20 s apart). An intake still not ingested when
the wait ends is not a failed farmer: it is approved, so the next run sees it as
approved; the farmer's later stages wait for that run, as they build on it. After the first such
intake no further farmer starts in the run, so one slow worker cannot burn the whole run.
An ingest in a failure status (INGEST_FAILED) stops the wait when the status holds for two polls in a
row or after INGEST_MAX_ATTEMPTS attempts (a single look can be a retry's intermediate state); it is
logged with its error columns and counted as a failed farmer. A later run reports an approved intake
whose ingest failed instead of skipping it as approved, and treats one whose ingest has not finished
as pending (its farmer's later stages and every later farmer wait for the next run).

Readiness: the job can start before the staff API accepts connections, so the
loader first polls the API's /ping (INTAKE_SEED_READY_TIMEOUT, default 240 s)
before its first call. A connection that is refused (nothing was sent) is
retried even for a request that must not be applied twice.

Location: the Livestock form requires the Location section's administrative
hierarchy. It is filled from the sample person's place in the pack's geography
(the kebele and its woreda, zone and region), the way the staff UI's geo-hierarchy
widget and the ODK transform write it, next to the holding's coordinates the
pack gives.

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

INTAKE_ARTIFACT = "registry.intake_form"
TRANSIENT_HTTP = (502, 503, 504)  # the gateway's answer when the service behind it is away
NETWORK_ATTEMPTS = 4
REQUEST_TIMEOUT = 30  # seconds per try


def job_started() -> float:
    """When the seed job's container started (epoch seconds), so the clock also counts the seed steps
    that run before this script. INTAKE_SEED_STARTED_AT overrides; otherwise PID 1's start time from /proc;
    otherwise now (the margin to the hook wait then has to cover the earlier steps)."""
    now = time.time()
    try:
        given = os.environ.get("INTAKE_SEED_STARTED_AT", "").strip()
        if given:
            started = float(given)
        else:
            with open("/proc/1/stat", encoding="ascii") as stat, open("/proc/uptime", encoding="ascii") as up:
                ticks = int(stat.read().rsplit(")", 1)[1].split()[19])  # field 22, starttime
                started = now - (float(up.read().split()[0]) - ticks / os.sysconf("SC_CLK_TCK"))
    except (OSError, ValueError, IndexError, AttributeError):
        return now
    return started if now - 3600 < started <= now else now  # an implausible value is ignored


STARTED = job_started()  # the time budget counts from here
# No request starts after STARTED + HARD_LIMIT seconds (INTAKE_SEED_HARD_LIMIT, default 720).
HARD_LIMIT = int(os.environ.get("INTAKE_SEED_HARD_LIMIT", "").strip() or 720)
# Ingest statuses that end an approved intake's ingest without the record: waiting on them is pointless.
# A failure status may be a retry's intermediate state: it ends a wait only when it holds for two polls in
# a row or the ingest has been attempted INGEST_MAX_ATTEMPTS times.
INGEST_FAILED = ("ERROR", "FAILED", "DEAD", "DEAD_LETTER")
INGEST_MAX_ATTEMPTS = 3
READY_TIMEOUT = int(os.environ.get("INTAKE_SEED_READY_TIMEOUT", "").strip() or 240)  # seconds to wait for the API
READY_POLL = 5  # seconds between looks at the API
# The root record of every intake the loader enters has an id only the loader makes (uuid5 of the sample
# person, the form and the year): a rerun resumes only its own intakes, never one somebody else entered.
SEED_RECORDS = uuid.UUID("5d3f0f8e-6c1a-4b7e-9a51-3c2f8e0d7a41")
TASK_PAGE_SIZE, TASK_PAGES = 100, 20
INGEST_POLL = 3  # seconds between looks at an approved intake's ingest
GEO_LEVELS = ("region", "zone", "woreda", "kebele")  # the levels under the country, in order
PACK = os.environ.get("SAMPLE_PACK", "ETH-OAN")
OPENG2P_DATA_DIR = Path(os.environ.get("OPENG2P_DATA_DIR", "/openg2p-data"))
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


class IngestFailed(RuntimeError):
    """An approved intake's ingest ended in a failure status."""


class IngestPending(RuntimeError):
    """An approved intake is not in the register yet; the next run finds it approved."""


class ReferencePending(RuntimeError):
    """The person's farmer reference waits for approval; the next run finds it decided."""


def log(message: str) -> None:
    print(f"[load-sample-data] {message}", flush=True)


def words(*parts) -> str:
    return " ".join(str(p) for p in parts if p not in (None, ""))


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


def location_section(chain: list[dict], root: str, pack_location: dict | None) -> dict | None:
    """The Location section row: the geo-hierarchy widget's document and lowest unit for the person's place,
    plus the holding's coordinates the pack gives. The country is not a level of the form's hierarchy:
    a place with no level below it (a country-level P-code) gives None; the caller then keeps only the
    pack's coordinates, if it has any."""
    levels = chain[1:] if chain and chain[0].get("level_id") == "l0" else chain
    hierarchy = [{"level_id": unit["level_id"], "level": level, "level_mnemonic": level,
                  "level_value_id": unit["level_value_id"], "level_value_mnemonic": unit["level_value_mnemonic"]}
                 for unit, level in zip(levels, GEO_LEVELS)]
    if not hierarchy:
        return None
    lowest = hierarchy[-1]["level_value_id"]
    row = {"internal_record_id": root, **(pack_location or {}), "geo_lowest_level_value_id": lowest,
           "geo_code_hierarchy_json": {"hierarchy": hierarchy, "lowest_level_value_id": lowest}}
    for entry in hierarchy:
        row[f"{entry['level']}_id"] = entry["level_value_id"]
    return row


def plan(people: list[dict], herds: list[dict], places: dict,
         new_id=lambda: str(uuid.uuid4())) -> list[dict]:
    """One entry per person with livestock samples: their Livestock intake."""
    by_id = {p["individual_id"]: p for p in people}
    planned = []
    for sample in herds:
        who = sample["individual_id"]
        person = by_id.get(who)
        if person is None:
            raise RuntimeError(f"livestock.json names {who}, who is not a sample person")
        if not person.get("national_id"):
            raise RuntimeError(f"{who} has no Fayda ID")
        stages = []
        for form, personnel_section, lists in STAGES:
            if not sample.get(lists[0][1]):
                raise RuntimeError(f"{who} has no animals; a Livestock record needs at least one")
            root = seed_record_id("livestock-sample", who, form)
            sections = {
                LOOKUP: [{"internal_record_id": root, "fayda_id": person["national_id"]}],
                personnel_section: [{"internal_record_id": root, **(sample.get("survey_personnel") or {})}],
            }
            if person.get("geo_pcode"):
                location = location_section(place_chain(places, person["geo_pcode"]), root, sample.get("location"))
                if location:
                    sections[LOCATION] = [location]
                elif sample.get("location"):
                    # An unknown P-code already fails in place_chain; a country-level one has no hierarchy,
                    # so only the pack's coordinates are kept.
                    log(f"{who}: {person['geo_pcode']} has no level below the country; "
                        "Location section with the pack's coordinates only")
                    sections[LOCATION] = [{"internal_record_id": root, **sample["location"]}]
                else:
                    log(f"{who}: {person['geo_pcode']} has no level below the country; no Location section")
            elif sample.get("location"):
                sections[LOCATION] = [{"internal_record_id": root, **sample["location"]}]
            for section, key in lists:
                rows = [{"internal_record_id": new_id(), "link_internal_record_id": root, **line}
                        for line in sample.get(key) or []]
                if rows:
                    sections[section] = rows
            stages.append({"form": form, "root": root, "sections": sections})
        planned.append({
            "individual_id": who, "foundational_id": person["national_id"], "birth_date": person.get("birth_date"),
            "gender": person.get("gender"), "name": words(person.get("given_name"), person.get("fathers_name")),
            "stages": stages,
        })
    return planned


def check_identity(fayda_id: str, farmer_id: str, found_birth, found_gender, birth, gender) -> None:
    """The Fayda number picked the reference; the birth date and gender must agree with the pack's person.
    A value the pack has but the farmer record lacks is a mismatch too."""
    who = f"farmer {farmer_id} for Fayda number {fayda_id}"
    if birth:
        if not found_birth:
            raise RuntimeError(f"{who} has no birth date, the pack's person {birth}; leaving it alone")
        if str(found_birth)[:10] != str(birth)[:10]:
            raise RuntimeError(f"{who} has birth date {found_birth}, the pack's person {birth}; leaving it alone")
    if gender:
        if not found_gender:
            raise RuntimeError(f"{who} has no gender, the pack's person {gender}; leaving it alone")
        if str(found_gender).strip().lower()[:1] != str(gender).strip().lower()[:1]:  # M / male
            raise RuntimeError(f"{who} has gender {found_gender}, the pack's person {gender}; leaving it alone")


def tls_context() -> ssl.SSLContext:
    """Certificates are checked unless INTAKE_SEED_VERIFY_TLS is false."""
    context = ssl.create_default_context()
    if os.environ.get("INTAKE_SEED_VERIFY_TLS", "true").strip().lower() == "false":
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    return context


class OutOfTime(RuntimeError):
    """The loader's time is used: what is left waits for the next seed run."""


def time_left() -> float:
    return STARTED + HARD_LIMIT - time.time()


def seed_record_id(*parts) -> str:
    """The id of a record only the loader enters: the same for the same sample on every run."""
    return str(uuid.uuid5(SEED_RECORDS, "/".join(str(p) for p in parts)))


def fetch(opener, request, timeout: int = REQUEST_TIMEOUT,
          attempts: int = NETWORK_ATTEMPTS) -> tuple[int, object, bytes]:
    """Status, headers and body; network errors and gateway statuses are retried with backoff.

    A request that must not be applied twice is sent with attempts=1. No try starts after the hard limit,
    and none waits longer than the time left. The query is left out of what is logged: IAM's callback
    carries a one-time code there.
    """
    where = f"{request.get_method()} {request.full_url.split('?', 1)[0]}"
    attempt = 0
    while True:
        attempt += 1
        left = time_left()
        if left <= 0:
            raise OutOfTime(f"{where}: not sent, the loader's {HARD_LIMIT}s are used")
        try:
            with opener.open(request, timeout=min(timeout, left)) as response:
                status, headers, body = response.status, response.headers, response.read()
        except urllib.error.HTTPError as exc:
            status, headers, body = exc.code, exc.headers, exc.read()
        except (urllib.error.URLError, OSError) as exc:
            # A refused connection delivered nothing, so even a request that must not be applied twice
            # may be sent again.
            refused = isinstance(getattr(exc, "reason", exc), ConnectionRefusedError)
            if attempt >= (max(attempts, NETWORK_ATTEMPTS) if refused else attempts):
                raise RuntimeError(f"{where}: {exc}") from exc
            status, headers, body = None, None, str(exc)
        if status is not None and (status not in TRANSIENT_HTTP or attempt >= attempts):
            return status, headers, body
        wait = min(2 ** attempt, max(0, time_left()))
        log(f"{where}: {status or body}; again in {wait:.0f}s")
        time.sleep(wait)


def wait_until_ready(api_url: str, timeout: int = READY_TIMEOUT, poll: float = READY_POLL) -> None:
    """Poll the staff API's /ping until it answers, for up to `timeout` seconds (the job can start before the
    API accepts connections). Returns when it never does: the first call then reports the failure."""
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=tls_context()))
    url = f"{api_url.rstrip('/')}/ping"
    deadline = time.time() + timeout
    while True:
        try:
            with opener.open(urllib.request.Request(url), timeout=min(REQUEST_TIMEOUT, max(1, time_left()))) as reply:
                if reply.status < 500:
                    log(f"staff API answers ({url})")
                    return
                problem = f"status {reply.status}"
        except urllib.error.HTTPError as exc:
            if exc.code < 500:  # the server is up; /ping may need no more than that
                log(f"staff API answers ({url}: {exc.code})")
                return
            problem = f"status {exc.code}"
        except (urllib.error.URLError, OSError) as exc:
            problem = str(exc)
        if time.time() >= deadline or time_left() <= 0:
            log(f"staff API not ready after {timeout}s ({url}: {problem}); going on")
            return
        log(f"staff API not ready ({problem}); looking again in {poll:.0f}s")
        time.sleep(min(poll, max(0.0, deadline - time.time())))


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

    def _send(self, path: str, data: bytes, content_type: str, attempts: int) -> tuple[int, dict]:
        for attempt in (1, 2):
            csrf = uuid.uuid4().hex
            request = urllib.request.Request(f"{self.api_url}{path}", data=data, method="POST", headers={
                "Authorization": f"Bearer {self._token}", "X-CSRF-Token": csrf, "Cookie": f"X-CSRF-Token={csrf}",
                "Content-Type": content_type})
            status, _, body = fetch(self._api, request, attempts=attempts)
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

    def post(self, path: str, payload: dict, once: bool = False) -> dict:
        """The response payload; `once` for a request that must not be applied twice (no network retry)."""
        envelope = {
            "request_header": {"sender_app_mnemonic": "livestock-db-seed", "sender_app_url": "http://db-seed",
                               "request_id": str(uuid.uuid4()),
                               "request_timestamp": datetime.now(timezone.utc).isoformat()},
            "request_body": {"request_payload": payload, "pagination_request": {"current_page": 1, "page_size": 100}},
        }
        status, reply = self._send(path, json.dumps(envelope).encode(), "application/json",
                                   1 if once else NETWORK_ATTEMPTS)
        header = reply.get("response_header") or {}
        if status != 200 or header.get("response_status") != "SUCCESS":
            raise RuntimeError(f"{path} as {self.username}: {status} {header.get('response_error_code')} "
                               f"{header.get('response_error_message')}")
        return (reply.get("response_body") or {}).get("response_payload") or {}


class Registry:
    """The registry database, read only: form metadata, the Farmer references, intake progress."""

    def __init__(self):
        import psycopg2  # only where the database is used; the tests run without it

        self.conn = psycopg2.connect(host=env("PGHOST"), port=os.environ.get("PGPORT", "5432"),
                                     dbname=env("PGDATABASE"), user=env("PGUSER"), password=env("PGPASSWORD"))
        self.conn.set_session(readonly=True, autocommit=True)  # the loader writes through the staff API only

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

    def farmer_reference(self, fayda_id: str, birth_date: str | None, gender: str | None,
                         individual_id: str | None = None) -> dict:
        """The approved Farmer reference for a Fayda number: read only.

        The reference is the Farmer registry's own record of the farmer, which arrived here through
        outgestion and was approved here; its Farmer ID was generated by the Farmer registry. Only
        references of the registry's configured Farmer source (COSS_FARMER_SOURCE_ID, the id the platform's
        own lookup uses; FARMER_REFERENCE_SOURCE_SYSTEM overrides) are considered. A reference an earlier
        loader wrote itself (its source record id is the pack's individual id) is not a Farmer reference.
        A missing or not yet approved reference is ReferencePending (the person waits for the next run)."""
        source = (os.environ.get("FARMER_REFERENCE_SOURCE_SYSTEM") or os.environ.get("COSS_FARMER_SOURCE_ID") or "").strip()
        found = self.rows("SELECT reference_id, farmer_id, local_farmer_id, state, source_record_id"
                          " FROM coss_farmer_references WHERE uid = %s" + (" AND source_system = %s" if source else "")
                          + " ORDER BY (state = 'APPROVED') DESC, reference_id", (fayda_id, source) if source else (fayda_id,))
        real = [row for row in found if not individual_id or row[4] != individual_id]
        if not real:
            if found:
                raise ReferencePending(f"the only farmer reference for Fayda number {fayda_id} was written by an earlier "
                                       "sample loader, not delivered by the Farmer registry; it needs the approved "
                                       "cleanup before the real reference can arrive")
            raise ReferencePending(f"no farmer reference for Fayda number {fayda_id} yet")
        approved = [row for row in real if row[3] == "APPROVED"]
        if len({row[1] for row in approved}) > 1:
            raise RuntimeError(f"more than one farmer reference for Fayda number {fayda_id}; leaving it alone")
        if not approved:
            state = real[0][3]
            if state == "PENDING":
                raise ReferencePending(f"the farmer reference for Fayda number {fayda_id} is PENDING, not APPROVED")
            raise RuntimeError(f"the farmer reference for Fayda number {fayda_id} is {state}, not APPROVED")
        reference_id, farmer_id, local_id, _, _ = approved[0]
        copy = self.rows("SELECT date_of_birth, gender FROM g2p_register_farmers WHERE internal_record_id = %s",
                         (local_id,))
        if not copy:
            raise ReferencePending(f"the farmer record of reference {reference_id} is not in the register yet")
        check_identity(fayda_id, farmer_id, copy[0][0], copy[0][1], birth_date, gender)
        return {"reference_id": reference_id, "farmer_id": farmer_id, "local_farmer_id": local_id}

    def stage_intakes(self, form_id: str, fin: str, root: str) -> list[tuple[str, str, str, str]]:
        """This person's intakes on the form, and the loader's own one by its root record id:
        (submission, draft, approval, root record)."""
        return [(str(sid), draft, approval, str(rid)) for sid, draft, approval, rid in self.rows(
            "SELECT s.submission_id, s.draft_status, s.approval_status, l.internal_record_id"
            " FROM g2p_intake_form_submissions s JOIN g2p_intake_form_livestocks l ON l.submission_id = s.submission_id"
            " WHERE s.form_id = %s AND (l.internal_record_id = %s OR l.fayda_fin = %s)", (form_id, root, fin))]

    def approval_status(self, submission_id: str) -> str | None:
        found = self.rows("SELECT approval_status FROM g2p_intake_form_submissions WHERE submission_id = %s",
                          (submission_id,))
        return found[0][0] if found else None

    def ingest_state(self, table: str, record_id: str, submission_id: str | None) -> tuple[str, str, int]:
        """("done" | "failed" | "waiting", detail, attempts): the intake's ingest status and error columns,
        or the loader's root record already in the register."""
        if submission_id:
            failure = self.ingest_failure(submission_id)
            if failure:
                return "failed", failure[0], failure[1]
            found = self.rows("SELECT register_ingest_process_status FROM g2p_intake_form_submissions"
                              " WHERE submission_id = %s", (submission_id,))
            if found and found[0][0] == "PROCESSED":
                return "done", "", 0
        if self.rows(f'SELECT 1 FROM "public"."{table}" WHERE internal_record_id = %s', (record_id,)):
            return "done", "", 0
        return "waiting", "", 0

    def ingest_failure(self, submission_id: str) -> tuple[str, int] | None:
        """(details, attempts) when the intake's ingest is in a failure status, else None."""
        found = self.rows("SELECT register_ingest_process_status, register_ingest_process_attempts,"
                          " left(coalesce(register_ingest_process_last_error_code, ''), 300)"
                          " FROM g2p_intake_form_submissions WHERE submission_id = %s", (submission_id,))
        if found and found[0][0] in INGEST_FAILED:
            return f"status {found[0][0]}, attempts {found[0][1]}, error {found[0][2]!r}", int(found[0][1] or 0)
        return None

    def ingest_pending(self, submission_id: str) -> bool:
        """An approved intake whose ingest has not finished (and is not in a failure status)."""
        found = self.rows("SELECT register_ingest_process_status FROM g2p_intake_form_submissions"
                          " WHERE submission_id = %s", (submission_id,))
        return bool(found) and found[0][0] not in ("PROCESSED", "NOT_APPLICABLE", *INGEST_FAILED)

    def wait_for(self, table: str, record_id: str, timeout: int, submission_id: str | None = None) -> None:
        deadline = time.time() + timeout
        failing = False
        while True:
            state, detail, attempts = self.ingest_state(table, record_id, submission_id)
            if state == "done":
                return
            if state == "failed":
                if failing or attempts >= INGEST_MAX_ATTEMPTS:
                    raise IngestFailed(f"ingest of intake {submission_id} failed: {detail}")
                failing = True
            else:
                failing = False
            if time.time() >= deadline:
                break
            time.sleep(min(INGEST_POLL, max(0.0, deadline - time.time())))
        stuck = self.rows(
            "SELECT register_ingest_process_status, register_ingest_process_attempts,"
            " left(coalesce(register_ingest_process_last_error_code, ''), 300) FROM g2p_intake_form_submissions"
            " WHERE approval_status = 'APPROVED' AND register_ingest_process_status <> 'PROCESSED'"
            + (" AND submission_id = %s" if submission_id else "")
            + " ORDER BY approved_at DESC LIMIT 1", (submission_id,) if submission_id else ())
        raise IngestPending(f"{table} {record_id} was not ingested within {timeout}s"
                            + (f" (latest unprocessed intake: {stuck[0]})" if stuck else ""))


# What a run reports: per sample farmer, then per stage intake.
COUNTERS = ("farmers referenced", "farmers failed", "farmers out of time",
            "farmers waiting for their farmer reference",
            "intakes submitted", "drafts completed", "intakes resumed at approval",
            "intakes approved and in the register", "intakes approved, ingest pending",
            "intakes approved, ingest failed", "intakes already approved",
            "intakes left for the next run")


class Loader:
    time_budget = 660  # seconds from the loader's start; INTAKE_SEED_TIME_BUDGET overrides
    ingest_slow = False  # set by the first intake whose ingest outlasts its wait

    def __init__(self, registry: Registry, submitter: StaffSession, approvers: list[StaffSession],
                 approve_timeout: int, ingest_timeout: int):
        self.registry, self.submitter, self.approvers = registry, submitter, approvers
        self.time_budget = int(os.environ.get("INTAKE_SEED_TIME_BUDGET", "").strip() or self.time_budget)
        self.approve_timeout, self.ingest_timeout = approve_timeout, ingest_timeout
        self.forms = registry.forms()

    def submit(self, stage: dict, submission_id: str | None = None) -> str:
        """Save every section (into the given draft, or a new one), then finalize.

        A draft a failed run leaves behind is found by its root record id and completed by the next run;
        saving a section replaces its rows. Finalizing is the platform's own step: it looks the declared
        Farmer ID and Fayda number up and links the approved Farmer reference."""
        form_id, register_id, registers = self.forms[stage["form"]]
        for section, rows in stage["sections"].items():
            # The save that creates the submission is sent once: a lost answer must not create a second
            # draft (the next run completes the first one, found by its own root record id).
            saved = self.submitter.post("/intake-form-data/save_intake_form_submission", {
                "submission_id": submission_id, "section_id": section, "section_payload": rows,
                "section_register_id": registers[section], "form_id": form_id, "register_id": register_id,
                "created_by": self.submitter.username, "documents": [],
            }, once=not submission_id)
            if not submission_id:
                submission_id = saved.get("submission_id")
                if not submission_id:
                    raise RuntimeError(f"saving {section} on {stage['form']} returned no submission")
        self.submitter.post("/intake-form-data/finalize_intake_form_submission", {
            "submission_id": submission_id, "register_id": register_id, "form_id": form_id}, once=True)
        return submission_id

    def approve(self, submission_id: str) -> None:
        """Approve the intake at whichever stage it has reached: stage 1 as the first approver, stage 2 as the
        second. A claim or decision whose answer is lost is not sent again; the task is read again."""
        deadline = min(time.time() + self.approve_timeout, STARTED + HARD_LIMIT)
        while self.registry.approval_status(submission_id) != "APPROVED":
            if time.time() > deadline:
                raise RuntimeError(f"intake {submission_id} is not approved within {self.approve_timeout}s")
            decided = False
            for stage, approver in enumerate(self.approvers, 1):
                task = self.open_task(approver, submission_id, stage)
                if task:
                    decided = self.decide(approver, task, submission_id, stage)
                    break
            if not decided:  # no task yet (AWE moves the intake on in the background), or the answer was lost
                time.sleep(3)

    @staticmethod
    def decide(approver: StaffSession, task: dict, submission_id: str, stage: int) -> bool:
        """True when the decision was accepted; a lost or refused one is logged and the task read again."""
        try:
            if task.get("status", "open") == "open":
                approver.post("/awe/claim_task", {"task_id": task["id"]}, once=True)
            approver.post("/awe/submit_task_decision", {
                "task_id": task["id"], "action": "approve", "comment": "Sample data (db-seed)",
                "artifact_id": submission_id, "artifact_type": INTAKE_ARTIFACT, "current_stage": stage}, once=True)
            log(f"      stage {stage} approved as {approver.username}")
            return True
        except OutOfTime:
            raise
        except RuntimeError as exc:
            log(f"      stage {stage} as {approver.username}: {exc}; reading the task again")
            return False

    @staticmethod
    def open_task(approver: StaffSession, submission_id: str, stage: int) -> dict | None:
        """The approver's open or claimed task for this intake and stage, looked up page by page."""
        for status in ("open", "claimed"):
            for page in range(1, TASK_PAGES + 1):
                tasks = approver.post("/awe/list_my_tasks", {"status": status, "artifact_type": INTAKE_ARTIFACT,
                                                             "page": page, "page_size": TASK_PAGE_SIZE})
                items = (tasks.get("data") or {}).get("items") or []
                task = next((t for t in items if t.get("artifact_id") == submission_id
                             and int(t.get("stage_order") or 0) == stage), None)
                if task:
                    return {"status": status, **task}
                if len(items) < TASK_PAGE_SIZE:
                    break
        return None

    def run(self, planned: list[dict]) -> dict:
        done = dict.fromkeys(COUNTERS, 0)
        stop_at = STARTED + self.time_budget
        for person in planned:
            if self.ingest_slow:  # one slow worker must not burn the whole run
                done["intakes left for the next run"] += len(person["stages"])
                continue
            accounted = 0  # this person's stage intakes counted as done, already approved or left over
            try:
                who = f"{person['individual_id']} {person['name']}"
                reference = self.registry.farmer_reference(person["foundational_id"], person["birth_date"],
                                                           person["gender"], person["individual_id"])
                done["farmers referenced"] += 1
                log(f"  {who}: farmer {reference['farmer_id']} (Farmer reference)")
                for position, stage_def in enumerate(person["stages"]):
                    stage = stage_def
                    if time.time() > stop_at:
                        done["intakes left for the next run"] += 1
                        accounted += 1
                        continue
                    form_id = self.forms[stage["form"]][0]
                    stage = self._with_farmer_id(stage, reference["farmer_id"])
                    previous = self.registry.stage_intakes(form_id, person["foundational_id"], stage["root"])
                    approved = [sid for sid, _, approval, _ in previous if approval == "APPROVED"]
                    failed = [(sid, self.registry.ingest_failure(sid)) for sid in approved]
                    failed = [(sid, found[0]) for sid, found in failed if found]
                    if failed:
                        remaining = len(person["stages"]) - position - 1
                        done["intakes approved, ingest failed"] += 1
                        done["intakes left for the next run"] += remaining
                        accounted += 1 + remaining
                        log(f"    {stage['form']}: INGEST FAILED for approved intake {failed[0][0]}: "
                            f"{failed[0][1]}; needs a look, not loaded")
                        break
                    if any(self.registry.ingest_pending(sid) for sid in approved):
                        accounted += self._ingest_pending(done, person, position,
                                                              "approved earlier, not yet in the register")
                        break
                    if any(approval == "APPROVED" for _, _, approval, _ in previous):
                        done["intakes already approved"] += 1
                        accounted += 1
                        log(f"    {stage['form']}: already approved")
                        continue
                    # Only the loader's own intakes (its root record id) are resumed or completed.
                    own = [(sid, status, approval) for sid, status, approval, rid in previous
                           if rid == stage["root"]]
                    waiting = next((sid for sid, status, approval in own
                                    if status == "FINAL" and approval == "PENDING"), None)
                    draft = next((sid for sid, status, _ in own if status == "DRAFT"), None)
                    if waiting:
                        submission_id = waiting
                        log(f"    {stage['form']}: intake {submission_id} waits for approval; approving it")
                        done["intakes resumed at approval"] += 1
                    elif draft:
                        submission_id = self.submit(stage, draft)
                        log(f"    {stage['form']}: draft intake {submission_id} completed and submitted")
                        done["drafts completed"] += 1
                    else:
                        submission_id = self.submit(stage)
                        log(f"    {stage['form']}: intake {submission_id} submitted")
                        done["intakes submitted"] += 1
                    self.approve(submission_id)
                    try:
                        self.registry.wait_for("g2p_register_livestocks", stage["root"],
                                               self.wait_time(self.ingest_timeout), submission_id)
                    except IngestPending as pending:
                        # Approved, only the ingest is slow: not a failed farmer. Its later stages build
                        # on this one, so they wait for the next run, which finds this one approved.
                        accounted += self._ingest_pending(done, person, position, str(pending))
                        break
                    done["intakes approved and in the register"] += 1
                    accounted += 1
                    log(f"    {stage['form']}: in the register")
            except Exception as exc:  # sample data must not fail the upgrade; the next run retries
                # Every stage not counted above is left for the next run, so the counters match the log.
                done["intakes left for the next run"] += len(person["stages"]) - accounted
                if isinstance(exc, ReferencePending):
                    done["farmers waiting for their farmer reference"] += 1
                    log(f"  {person['individual_id']}: waiting, left for the next run: {exc}")
                elif isinstance(exc, OutOfTime) or time_left() <= 0:
                    done["farmers out of time"] += 1
                    log(f"  {person['individual_id']}: out of time, left for the next run: {exc}")
                else:
                    done["farmers failed"] += 1
                    log(f"  {person['individual_id']}: FAILED, left for the next run: {exc!r}")
        if done["intakes left for the next run"]:
            log(f"time budget of {self.time_budget}s used: {done['intakes left for the next run']} stage intakes "
                "are left for the next seed run")
        return done

    def _ingest_pending(self, done: dict, person: dict, position: int, why: str) -> int:
        """An approved intake not yet in the register: its farmer's later stages and every later farmer
        wait for the next run. Returns how many of the farmer's stages this accounts for."""
        remaining = len(person["stages"]) - position - 1
        self.ingest_slow = True
        done["intakes approved, ingest pending"] += 1
        done["intakes left for the next run"] += remaining
        log(f"    {person['stages'][position]['form']}: ingest pending ({why}); "
            f"{remaining} later stages left for the next run")
        return 1 + remaining

    def wait_time(self, timeout: int) -> int:
        """`timeout`, cut to what is left before the hard limit."""
        return max(1, min(timeout, int(time_left())))

    @staticmethod
    def _with_farmer_id(stage: dict, farmer_id: str) -> dict:
        """The stage with the Farmer ID of the Farmer reference: the one the Farmer registry generated."""
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
    planned = plan(pack.read("individuals.json"), herds, pack.places())
    animals = sum(len(s["sections"].get(STAGES[0][2][0][0], [])) for p in planned for s in p["stages"])
    log(f"{len(planned)} sample farmers with livestock, {animals} animal rows, from {pack.root}")

    iam, api, password = staff_iam_url(), env("STAFF_API_URL"), env("INTAKE_SEED_PASSWORD")
    log(f"staff IAM {iam}")
    wait_until_ready(api)
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
            int(env("INTAKE_SEED_APPROVE_TIMEOUT", "180")), int(env("INTAKE_SEED_INGEST_TIMEOUT", "420")))
        done = loader.run(planned)
    finally:
        registry.conn.close()
    log("Done: " + ", ".join(f"{count} {what}" for what, count in done.items()) + ".")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # a setting, the database or a sign-in: logged; the upgrade goes on
        print(f"[load-sample-data] FAILED before loading sample data, none loaded: {exc!r}", file=sys.stderr)
