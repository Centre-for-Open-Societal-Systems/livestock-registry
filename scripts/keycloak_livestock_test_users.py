#!/usr/bin/env python3
"""Create (or refresh) the livestock approval-chain test users in a Keycloak realm.

The approval chain assigns each stage through /livestock/approver-resolver,
which looks for users that hold the level's client role on the staff-portal
client AND carry an ``approver_location_value`` attribute equal to the
record's kebele / woreda / zone / region (approver_resolver_service.py).
The local compose stack gets these users from local/keycloak/realm-staff.json;
a cluster Keycloak has to be given them explicitly - that is what this does.
Idempotent: existing roles/users are updated, nothing is duplicated.

Usage (Keycloak master-realm admin, standard library only):
  KC_BASE_URL=https://keycloak-livestock-development.oanstaging.com \
  KC_ADMIN_USER=admin KC_ADMIN_PASSWORD=... \
  python3 scripts/keycloak_livestock_test_users.py            # create/refresh
  python3 scripts/keycloak_livestock_test_users.py --delete   # remove them again

Optional: KC_REALM (staff), KC_CLIENT_ID (livestock-staff-portal),
USERS_PASSWORD (test1234), USER_SUFFIX (.test), KC_ADMIN_REALM (master),
KC_INSECURE=1 to skip TLS verification.

KC_CLIENT_ID must be the staff-portal client of THAT deployment: the chart
names it after the release (<release>-staff-portal, e.g.
livestock-registry-staff-portal on dev); only the compose stack uses
livestock-staff-portal. The resolver looks the roles up on the same client
(registry setting keycloak_client_id), so the two must agree.
"""
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("KC_BASE_URL", "").rstrip("/")
REALM = os.environ.get("KC_REALM", "staff")
ADMIN_REALM = os.environ.get("KC_ADMIN_REALM", "master")
CLIENT_ID = os.environ.get("KC_CLIENT_ID", "livestock-staff-portal")
PASSWORD = os.environ.get("USERS_PASSWORD", "test1234")
SUFFIX = os.environ.get("USER_SUFFIX", ".test")
LOCATION_ATTR = "approver_location_value"

# username stem, client role, approver_location_value (None = no scoping attribute)
USERS = [
    ("field.officer", "Field Officer", None),
    ("kebele.approver", "Kebele Approver", "Dire Arerti"),
    ("woreda.approver", "Woreda Approver", "Ada'a"),
    ("zone.approver", "Zone Approver", "East Shewa"),
    ("region.approver", "Region Approver", "Oromia"),
]

_ctx = ssl._create_unverified_context() if os.environ.get("KC_INSECURE") else None
_token = None


def call(method, path, body=None, form=None, raw=False):
    url = BASE + path
    data = None
    headers = {"Accept": "application/json"}
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if _token:
        headers["Authorization"] = "Bearer " + _token
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60, context=_ctx) as r:
            payload = r.read()
            if raw:
                return r.status, r.headers, payload
            return r.status, (json.loads(payload) if payload else None)
    except urllib.error.HTTPError as e:
        payload = e.read()
        if raw:
            return e.code, e.headers, payload
        try:
            return e.code, json.loads(payload)
        except Exception:
            return e.code, payload.decode(errors="replace")


def login():
    global _token
    user, pw = os.environ.get("KC_ADMIN_USER"), os.environ.get("KC_ADMIN_PASSWORD")
    if not (BASE and user and pw):
        sys.exit("KC_BASE_URL, KC_ADMIN_USER and KC_ADMIN_PASSWORD are required")
    st, d = call("POST", f"/realms/{ADMIN_REALM}/protocol/openid-connect/token",
                 form={"grant_type": "password", "client_id": "admin-cli", "username": user, "password": pw})
    if st != 200:
        sys.exit(f"admin login failed ({st}): {d}")
    _token = d["access_token"]


def client_uuid():
    st, d = call("GET", f"/admin/realms/{REALM}/clients?clientId={urllib.parse.quote(CLIENT_ID)}")
    if st != 200 or not d:
        sys.exit(f"client {CLIENT_ID!r} not found in realm {REALM!r} ({st}): {d}\n"
                 f"Set KC_CLIENT_ID to this deployment's staff-portal client "
                 f"(the chart names it <release>-staff-portal, e.g. livestock-registry-staff-portal).")
    return d[0]["id"]


def ensure_role(cid, name):
    st, d = call("GET", f"/admin/realms/{REALM}/clients/{cid}/roles/{urllib.parse.quote(name)}")
    if st == 200:
        return d, False
    st, _ = call("POST", f"/admin/realms/{REALM}/clients/{cid}/roles", body={"name": name})
    if st not in (201, 204):
        sys.exit(f"could not create role {name!r} ({st})")
    st, d = call("GET", f"/admin/realms/{REALM}/clients/{cid}/roles/{urllib.parse.quote(name)}")
    return d, True


def find_user(username):
    st, d = call("GET", f"/admin/realms/{REALM}/users?username={urllib.parse.quote(username)}&exact=true")
    return (d or [None])[0] if st == 200 else None


def ensure_user(username, attr_value):
    rep = {
        "username": username, "enabled": True, "emailVerified": True,
        "email": f"{username}@example.com",
        "firstName": username.split(".")[0].capitalize(),
        "lastName": " ".join(p.capitalize() for p in username.split(".")[1:]),
        "attributes": {LOCATION_ATTR: [attr_value]} if attr_value else {},
    }
    u = find_user(username)
    if u:
        attrs = dict(u.get("attributes") or {})
        if attr_value:
            attrs[LOCATION_ATTR] = [attr_value]
        else:
            attrs.pop(LOCATION_ATTR, None)
        st, _ = call("PUT", f"/admin/realms/{REALM}/users/{u['id']}", body={"enabled": True, "attributes": attrs})
        created = False
    else:
        st, _ = call("POST", f"/admin/realms/{REALM}/users", body=rep)
        if st != 201:
            sys.exit(f"could not create user {username!r} ({st})")
        u = find_user(username)
        created = True
    call("PUT", f"/admin/realms/{REALM}/users/{u['id']}/reset-password",
         body={"type": "password", "value": PASSWORD, "temporary": False})
    return u, created


def main():
    login()
    cid = client_uuid()
    delete = "--delete" in sys.argv
    for stem, role, loc in USERS:
        username = stem + SUFFIX
        if delete:
            u = find_user(username)
            if u:
                call("DELETE", f"/admin/realms/{REALM}/users/{u['id']}")
                print(f"deleted  {username}")
            else:
                print(f"absent   {username}")
            continue
        role_rep, role_new = ensure_role(cid, role)
        u, created = ensure_user(username, loc)
        st, _ = call("POST", f"/admin/realms/{REALM}/users/{u['id']}/role-mappings/clients/{cid}", body=[role_rep])
        print(f"{'created' if created else 'updated'}  {username:<26} role={role!r}{' (role created)' if role_new else ''}"
              f"{'  ' + LOCATION_ATTR + '=' + repr(loc) if loc else ''}")
    if not delete:
        print(f"done: realm={REALM} client={CLIENT_ID} password={'*' * len(PASSWORD)} (users can log in to the staff portal)")


if __name__ == "__main__":
    main()
