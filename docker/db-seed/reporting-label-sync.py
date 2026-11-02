#!/usr/bin/env python3
"""Copy the code-list labels the reporting views show from Master Data into lr_rpt_label.

lr_rpt_animal carries species and breed as the codes the register stores
(CATTLE, BREED_LOCAL) and their labels for the dashboards (species_name,
breed_name). The labels live in Master Data, a separate service with its own
database, so they are read through its catalogue API with a client-credentials
token, the way the farmer registry's reporting reads its geography
(farmer-extension/reporting/sync_geo_levels.py), and copied here. The lists are
small and replaced whole, in one transaction, so a reader never sees a
half-filled table.

Environment:
  PGHOST PGPORT PGDATABASE PGUSER PGPASSWORD    the registry database (libpq)
  MDS_API_URL MDS_TOKEN_URL MDS_CLIENT_ID MDS_CLIENT_SECRET
                                                Master Data API and the service
                                                account it accepts; unset skips
                                                the copy

Skipping is not a failure: the views still build and show the code where a
label is missing. A Master Data that refuses or answers without the lists
leaves the previous labels in place and exits non-zero, so the job log says so.
"""
import json
import os
import sys
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

LISTS = ("LIVESTOCK_SPECIES", "LIVESTOCK_BREED")
PAGE_SIZE = 500
MAX_PAGES = 20


class LabelsUnavailable(RuntimeError):
    pass


def post(url, body, *, token=None, form=False):
    headers = {"Content-Type": "application/x-www-form-urlencoded" if form else "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    data = urlencode(body).encode() if form else json.dumps(body).encode()
    try:
        with urlopen(Request(url, data=data, headers=headers, method="POST"), timeout=30) as response:
            return json.load(response)
    except Exception:
        raise LabelsUnavailable("Master Data labels unavailable; previous labels retained") from None


def labels_of(values):
    """(code, label) pairs of one list's catalogue values: active ones only,
    keyed by value_code and, when it differs, by value_id too (the register
    stores whichever the form's widget wrote)."""
    pairs = {}
    for value in values or []:
        if not isinstance(value, dict) or str(value.get("status") or "ACTIVE").upper() != "ACTIVE":
            continue
        label = str(value.get("display") or value.get("value_display") or "").strip()
        if not label:
            continue
        for key in (value.get("value_code"), value.get("value_id")):
            key = str(key or "").strip()
            if key:
                pairs.setdefault(key, label)
    return sorted(pairs.items())


def fetch_labels(api_url, token_url, client_id, client_secret, lists=LISTS):
    """{list_code: [(code, label)]} from the Master Data catalogue."""
    token = post(token_url, {"grant_type": "client_credentials", "client_id": client_id,
                             "client_secret": client_secret}, form=True).get("access_token")
    if not token:
        raise LabelsUnavailable("Master Data reporting authentication refused")
    found = {}
    for list_code in lists:
        values = []
        for page in range(1, MAX_PAGES + 1):
            body = post(api_url.rstrip("/") + "/catalogue/get_list_values", {
                "request_header": {"sender_app_mnemonic": "oan-livestock-reporting", "sender_app_url": "",
                                   "request_id": uuid4().hex,
                                   "request_timestamp": datetime.now(timezone.utc).isoformat()},
                "request_body": {"pagination_request": {"current_page": page, "page_size": PAGE_SIZE},
                                 "request_payload": {"list_code": list_code}}}, token=token)
            if str((body.get("response_header") or {}).get("response_status") or "").upper() != "SUCCESS":
                raise LabelsUnavailable(f"Master Data refused the {list_code} list")
            rows = ((body.get("response_body") or {}).get("response_payload") or {}).get("values") or []
            values.extend(rows)
            if len(rows) < PAGE_SIZE:
                break
        pairs = labels_of(values)
        if not pairs:
            raise LabelsUnavailable(f"Master Data has no active values in {list_code}")
        found[list_code] = pairs
    return found


TABLE = """CREATE TABLE IF NOT EXISTS lr_rpt_label (
    list_code text NOT NULL,
    code      text NOT NULL,
    label     text NOT NULL,
    PRIMARY KEY (list_code, code)
)"""


def store(found):
    import psycopg2

    with psycopg2.connect("") as connection, connection.cursor() as cursor:
        cursor.execute(TABLE)
        cursor.execute("DELETE FROM lr_rpt_label WHERE list_code = ANY(%s)", (list(found),))
        for list_code, pairs in found.items():
            cursor.executemany("INSERT INTO lr_rpt_label (list_code, code, label) VALUES (%s, %s, %s)",
                               [(list_code, code, label) for code, label in pairs])


def main():
    settings = [os.environ.get(name, "") for name in ("MDS_API_URL", "MDS_TOKEN_URL", "MDS_CLIENT_ID", "MDS_CLIENT_SECRET")]
    if not all(settings):
        print("[reporting-label-sync] Master Data API not configured; lr_rpt_label left as it is", file=sys.stderr)
        return 0
    found = fetch_labels(*settings)
    store(found)
    print("[reporting-label-sync] " + ", ".join(f"{code}: {len(pairs)}" for code, pairs in found.items()))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except LabelsUnavailable as error:
        print(f"[reporting-label-sync] {error}", file=sys.stderr)
        sys.exit(1)
