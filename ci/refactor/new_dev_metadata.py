"""Read effective New Dev registry metadata via its standard IAM SSO session.

No register records, documents, secrets, business intakes or approval actions
are queried. Credentials/cookies stay in memory. Only metadata read operations
may be posted to the registry. Saved metadata removes credential/query secrets.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from html.parser import HTMLParser
import http.cookiejar
import json
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request
from uuid import uuid4

_parents = Path(__file__).resolve().parents
ROOT = _parents[2] if len(_parents) > 2 else Path("/work")
IAM = "https://staff-iam.development.oanstaging.com"
KEYCLOAK = "keycloak.development.oanstaging.com"


class Form(HTMLParser):
    def __init__(self):
        super().__init__()
        self.action = None
        self.fields = {}
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form" and attrs.get("id") == "kc-form-login":
            self.action = attrs.get("action")
        if tag == "input" and attrs.get("name") and attrs.get("type") == "hidden":
            self.fields[attrs["name"]] = attrs.get("value", "")


def sanitize(value):
    if isinstance(value, dict):
        return {key:("<redacted>" if re.search(r"password|client.?secret|access.?token|private.?key|authorization", key, re.I)
                    and isinstance(item, str) else sanitize(item)) for key,item in value.items()}
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, str) and value.startswith(("https://", "http://")):
        parsed = urllib.parse.urlsplit(value)
        query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        if parsed.username or parsed.password or any(re.search(r"token|secret|password|api.?key", key, re.I) for key,_ in query):
            host = parsed.hostname or ""
            if parsed.port:
                host += ":" + str(parsed.port)
            value = urllib.parse.urlunsplit((parsed.scheme, host, parsed.path,
                urllib.parse.urlencode([(key,"<redacted>") for key,_ in query]), parsed.fragment))
    return value


class Reader:
    def __init__(self, domain, credential_file=None):
        self.credential_file = credential_file or ROOT / "secrets/environments/new-dev/credentials.txt"
        self.domain = domain
        short = "crop" if domain == "cropsown" else domain
        self.base = f"https://staff-{short}.development.oanstaging.com"
        self.ui = f"https://{short}-registry.development.oanstaging.com"
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies))
        self.calls = []

    def request(self, url, *, data=None, headers=None):
        request = urllib.request.Request(url, data=data, headers=headers or {})
        try:
            with self.opener.open(request, timeout=20) as response:
                body = response.read()
                self.calls.append({"method":request.get_method(), "path":urllib.parse.urlsplit(url).path,
                                   "status":response.status})
                return body
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"HTTP {error.code}: {urllib.parse.urlsplit(url).path}") from None

    def login(self):
        credentials = {}
        path = self.credential_file
        for line in path.read_text().splitlines():
            match = re.match(r"^\s*(user|password)\s*[:=]\s*(.+?)\s*$",line,re.I)
            if match:
                credentials[match[1].lower()] = match[2]
        if set(credentials) != {"user", "password"}:
            raise RuntimeError("New Dev staff credential labels are unavailable")
        url = IAM + "/auth/start_authentication_transaction?" + urllib.parse.urlencode({"id":1,"redirect_uri":self.ui})
        transaction = json.loads(self.request(url, data=b""))
        auth_url = transaction["redirectUrl"]
        if urllib.parse.urlsplit(auth_url).hostname != KEYCLOAK:
            raise RuntimeError("Unexpected New Dev identity provider")
        parser = Form()
        parser.feed(self.request(auth_url).decode())
        if not parser.action or urllib.parse.urlsplit(parser.action).hostname != KEYCLOAK:
            raise RuntimeError("Standard Keycloak credential form was not returned")
        self.request(parser.action, data=urllib.parse.urlencode({**parser.fields,
            "username":credentials["user"], "password":credentials["password"], "credentialId":""}).encode(),
            headers={"Content-Type":"application/x-www-form-urlencoded"})
        # Identity response is deliberately discarded rather than published.
        json.loads(self.request(IAM + "/auth/get_logged_in_user"))

    def read(self, path, payload, *, page=1, size=100):
        if not re.fullmatch(r"/(?:register-metadata|register-section-metadata|register-tab-metadata|intake-form-metadata|data-model|registry-language|registry-theme|ingestion-config|outgestion-config)/get_[a-z_]+",path) and path != "/register-data/get_schema_definition_for_register_section":
            raise RuntimeError("Only registry metadata reads are allowed")
        body = {"request_header":{"sender_app_mnemonic":"COSS_REFACTOR_AUDIT", "sender_app_url":self.ui,
            "request_id":str(uuid4()),"request_timestamp":datetime.now(timezone.utc).isoformat()},
            "request_body":{"request_payload":payload,"pagination_request":{"current_page":page,"page_size":size}}}
        headers = {"Content-Type":"application/json", "Origin":self.ui, "Referer":self.ui + "/"}
        csrf = [cookie.value for cookie in self.cookies if cookie.name == "X-CSRF-Token"]
        if len(csrf) != 1:
            raise RuntimeError("Native IAM CSRF session is unavailable or ambiguous")
        headers["X-CSRF-Token"] = csrf[0]
        return json.loads(self.request(self.base + path, data=json.dumps(body).encode(), headers=headers))

    def payload(self, path, payload):
        response = self.read(path, payload)
        header = response.get("response_header", {})
        if header.get("response_error_code") or header.get("response_status") not in {"SUCCESS", "SUCC", "success"}:
            # Successful native variants sometimes use an empty error string;
            # never accept an error envelope as an empty metadata catalogue.
            if header.get("response_error_code") or "response_body" not in response:
                raise RuntimeError("Metadata error envelope: " + path)
        return response["response_body"]["response_payload"]

    def pages(self, path, payload):
        result = []
        for page in range(1, 1001):
            response = self.read(path, payload, page=page)
            header = response.get("response_header", {})
            if header.get("response_error_code"):
                raise RuntimeError("Metadata error envelope: " + path)
            body = response["response_body"]
            items = body["response_payload"]
            if not isinstance(items, list):
                raise RuntimeError("Expected metadata list: " + path)
            result.extend(items)
            pagination = body.get("pagination_response") or {}
            if page >= pagination.get("number_of_pages", 1):
                return result
        raise RuntimeError("Metadata pagination limit")

    def snapshot(self):
        result = {"registry":self.domain,"source_url":self.base,"captured_at":datetime.now(timezone.utc).isoformat(),
                  "authenticated":True,"scope":"Metadata only; no register/intake/document records", "registers":[],
                  "forms":[],"errors":[]}
        for definition in self.pages("/register-metadata/get_all_registers", {}):
            ident = definition["register_id"]
            entry = {"definition":definition}
            result["registers"].append(entry)
            for key, endpoint in (("fields","/register-metadata/get_register_fields"),
                                  ("schema","/register-metadata/get_register_schema")):
                entry[key] = self.payload(endpoint, {"register_id":ident})
            entry["sections"] = self.pages("/register-section-metadata/get_all_sections", {"register_id":ident})
            entry["tabs"] = self.pages("/register-tab-metadata/get_all_tabs", {"register_id":ident})
            for tab in entry["tabs"]:
                tab["sections"] = self.pages("/register-tab-metadata/get_sections", {"tab_id":tab["tab_id"]})
            print(json.dumps({"registry":self.domain,"register":definition["register_mnemonic"],
                              "sections":len(entry["sections"]),"tabs":len(entry["tabs"])}),flush=True)
        for form in self.pages("/intake-form-metadata/get_all_intake_forms", {}):
            entry = dict(form)
            result["forms"].append(entry)
            entry["tabs"] = self.pages("/intake-form-metadata/get_all_tabs", {"form_id":form["form_id"]})
            for tab in entry["tabs"]:
                tab["sections"] = self.pages("/intake-form-metadata/get_all_sections", {"tab_id":tab["tab_id"]})
        for key,path in (("themes","/registry-theme/get_all_themes"),
                         ("languages","/registry-language/get_all_languages"),
                         ("data_models","/data-model/get_all_data_models")):
            result[key] = self.pages(path, {})
        result["calls"] = self.calls
        return sanitize(result)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("domain", choices=("cropsown","livestock"))
    parser.add_argument("--capture", action="store_true")
    parser.add_argument("--pipeline", action="store_true")
    parser.add_argument("--credentials",type=Path,help="Local authorized credential file; values remain in memory")
    args = parser.parse_args()
    portable = (ROOT / f"{args.domain}-extension").is_dir()
    if portable and not args.credentials:
        parser.error("--credentials is required for an explicit authorized live metadata capture")
    repo = ROOT if portable else ROOT / f"OAN/worktrees/{args.domain}-registry/develop-refactor"
    reader = Reader(args.domain,args.credentials)
    reader.login()
    if args.pipeline:
        output = repo / "ci-output/refactor/new-dev/pipeline-metadata.json"
        result = {"registry":args.domain,"captured_at":datetime.now(timezone.utc).isoformat(),"metadata":{},"errors":[]}
        for path in ("/ingestion-config/get_all_incoming_key_paths", "/ingestion-config/get_all_semantic_patterns",
                     "/ingestion-config/get_all_register_semantic_patterns", "/ingestion-config/get_all_templates",
                     "/outgestion-config/get_all_templates"):
            try:
                result["metadata"][path] = reader.pages(path,{})
            except RuntimeError as error:
                result["errors"].append({"path":path,"error":str(error)})
        result["calls"] = reader.calls
        output.write_text(json.dumps(sanitize(result),indent=2,ensure_ascii=False)+"\n",encoding="utf-8",newline="\n")
        print(json.dumps({"registry":args.domain,"counts":{name:len(rows) for name,rows in result["metadata"].items()},"errors":result["errors"]}))
        return
    if args.capture:
        result = reader.snapshot()
        output = repo / "ci-output/refactor/new-dev"
        output.mkdir(parents=True, exist_ok=True)
        path = output / "metadata.json"
        path.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8",newline="\n")
        print(json.dumps({"saved":str(path.relative_to(ROOT)),"registers":len(result["registers"]),"forms":len(result["forms"])}))
        return
    result = reader.read("/register-metadata/get_all_registers", {})
    def shape(value):
        if isinstance(value,dict):
            return {key:shape(item) for key,item in value.items()}
        if isinstance(value,list):
            return {"count":len(value),"item":shape(value[0]) if value else None}
        return type(value).__name__
    print(json.dumps({"domain":args.domain,"authenticated":True,"register_response_shape":shape(result)},indent=2))


if __name__ == "__main__":
    main()
