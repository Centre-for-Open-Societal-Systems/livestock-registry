"""Linux CI-only real HTTP gate against the saved synthetic Postman dependency.

Reuses the built profile image. Test containers share the runner loopback solely
so the CLI's localhost listener is reachable; PostgreSQL publishes only an
ephemeral loopback port. No proxy, live endpoint or credential is configured.
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlsplit

WORKFLOW = (
    "test_native_http_add_routes_only_functional_woreda_approver_without_identity_writes",
    "test_native_http_update_routes_old_geography_and_retry_reuses_remote_request",
    "test_native_http_directory_failure_blocks_with_visible_diagnostic_and_bounded_retries",
)
LOOKUP = (
    "test_signed_pair_lookup_filters_profile_and_preserves_explicit_clear",
    "test_optional_omission_is_distinct_from_explicit_clear",
    "test_transport_failures_are_blocking_and_redirects_are_not_followed",
    "test_signature_correlation_consent_cardinality_and_freshness_fail_closed",
    "test_source_contract_gaps_are_explicit_and_fin_is_not_converted",
    "test_server_pinned_key_id_cannot_be_changed_by_source",
    "test_current_lookup_pins_immutable_person_and_allows_source_approved_uid_rotation",
    "test_fin_only_signed_http_lookup_resolves_farmer_id_without_inventing_fan",
    "test_fin_http_no_match_is_pending_eligible_but_mismatch_is_refused",
)
NOTIFICATION = "test_notification_uses_actual_configured_signed_lookup_over_http"


def groups(domain):
    prefix = f"{domain}-extension/tests/"
    def nodes(file, cls, names):
        return [prefix + file + "::" + cls + "::" + name for name in names]
    return [
        nodes("test_farmer_reference_http.py", "HttpLookupTests", LOOKUP),
        nodes("test_farmer_reference_native.py", "NativeReferenceTests", WORKFLOW),
        nodes("test_farmer_reference_notification_native.py", "NativeReferenceTests", WORKFLOW)
        + nodes("test_farmer_reference_notification_native.py", "NativeNotificationTests", (*WORKFLOW, NOTIFICATION)),
    ]


def main(domain):
    if sys.platform != "linux":
        raise RuntimeError("The bounded HTTP gate requires a disposable Linux CI runner; no local Docker fallback")
    repo = Path(__file__).resolve().parents[2]
    evidence = repo / "ci-output/refactor/signed-http"
    evidence.mkdir(parents=True, exist_ok=True)
    image = os.environ.get("COSS_REFACTOR_TEST_IMAGE", "registry-reference-tests")
    owner = "signed-http-" + uuid.uuid4().hex
    label = "coss-refactor.owner"
    owned = []
    simulation = None
    traffic = {"requests": 0, "methods": {}, "statuses": {}}
    listening = threading.Event()
    address = {}
    report = {"registry": domain, "verification_complete": False, "groups": [],
              "distinct_behaviors": 13, "expected_executions": 19,
              "raw_traffic_saved": False, "history_published": False,
              "live_kafka_awe_acceptance": "NOT RUN", "traffic": traffic}

    def run(*args, timeout=180):
        result = subprocess.run(args, check=False, cwd=repo, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=timeout)
        if result.returncode:
            # Only fixture/test diagnostics; never persist raw HTTP events.
            raise RuntimeError(f"{args[0]} failed ({result.returncode}): " + (result.stderr or result.stdout)[-5000:])
        return result.stdout.strip()

    def create(*options):
        ident = run("docker", "create", "--label", f"{label}={owner}", *options)
        owned.append(ident)
        return ident

    def consume():
        for line in simulation.stdout:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get("event") == "listening":
                address.update(event)
                listening.set()
            elif event.get("event") == "request":
                traffic["requests"] += 1
                for key, field in (("methods", "method"), ("statuses", "statusCode")):
                    value = str(event.get(field))
                    traffic[key][value] = traffic[key].get(value, 0) + 1

    try:
        # Fail before starting resources if the reusable image or CLI is absent.
        report["image_id"] = run("docker", "image", "inspect", image, "--format", "{{.Id}}")
        postman = shutil.which("postman")
        if not postman:
            raise RuntimeError("Postman CLI with simulation support is required")
        report["postman_version"] = run(postman, "--version")
        simulation = subprocess.Popen([postman, "simulation", "run",
            "postman/simulations/farmer-reference.sim.yaml", "--port", "auto",
            "--no-history", "--output", "ndjson"], cwd=repo, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
            start_new_session=True)
        reader = threading.Thread(target=consume, daemon=True)
        reader.start()
        deadline = time.monotonic() + 30
        while not listening.wait(0.1):
            if simulation.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError("Synthetic Postman dependency did not reach listening")
        members = address.get("mocks", [])
        if len(members) != 1 or members[0].get("routeKey") != "farmer":
            raise RuntimeError("Unexpected simulation members")
        base = members[0]["address"]
        parsed = urlsplit(base)
        if parsed.scheme != "http" or parsed.hostname not in ("localhost", "127.0.0.1") or parsed.path != "/farmer":
            raise RuntimeError("Simulation returned a non-loopback or unexpected dependency URL")
        report["dependency"] = "saved synthetic farmer member over runner loopback"
        database = create("--memory=256m", "-p", "127.0.0.1::5432",
                          "-e", "POSTGRES_HOST_AUTH_METHOD=trust", "postgres:15-alpine")
        run("docker", "start", database)
        for _ in range(60):
            ready = subprocess.run(["docker", "exec", database, "pg_isready", "-h", "127.0.0.1", "-U", "postgres"], check=False, capture_output=True, timeout=10)
            if ready.returncode == 0:
                break
            time.sleep(0.25)
        else:
            raise RuntimeError("Owned PostgreSQL did not become ready")
        ports = json.loads(run("docker", "inspect", database, "--format", "{{json .NetworkSettings.Ports}}"))
        mapping = ports["5432/tcp"]
        if len(mapping) != 1 or mapping[0]["HostIp"] != "127.0.0.1":
            raise RuntimeError("PostgreSQL must publish only to runner loopback")
        port = int(mapping[0]["HostPort"])
        executed = []
        for index, nodes in enumerate(groups(domain)):
            dbname = f"signed_http_{index}"
            run("docker", "exec", database, "createdb", "-U", "postgres", dbname)
            xmlname = f"group-{index}.xml"
            before = traffic["requests"]
            test = create("--user", f"{os.getuid()}:{os.getgid()}", "--memory=768m",
                "--network", "host", "--entrypoint", "python", "-w", "/work",
                "-v", f"{repo.as_posix()}:/work:ro", "-v", f"{evidence.as_posix()}:/evidence",
                "-e", f"REGISTRY_EXTENSION_MODULE=openg2p_registry_{domain}_extension",
                "-e", f"PYTHONPATH=/work/{domain}-extension/src",
                "-e", f"FARMER_TEST_DATABASE_URL=postgresql+asyncpg://postgres@127.0.0.1:{port}/{dbname}",
                "-e", f"FARMER_SIMULATION_URL={base}", "-e", f"FARMER_WORKFLOW_SIMULATION_URL={base}",
                image, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                f"--junitxml=/evidence/{xmlname}", *nodes)
            output = run("docker", "start", "--attach", test, timeout=240)
            (evidence / f"group-{index}.txt").write_text(output + "\n", encoding="utf-8")
            state = json.loads(run("docker", "inspect", test, "--format", "{{json .State}}"))
            if state["ExitCode"] != 0:
                raise RuntimeError(f"HTTP group {index} exited {state['ExitCode']}")
            cases = list(ET.parse(evidence / xmlname).iter("testcase"))
            actual = [case.attrib["name"] for case in cases]
            expected = [node.rsplit("::", 1)[1] for node in nodes]
            if sorted(actual) != sorted(expected) or any(list(case) for case in cases):
                raise RuntimeError(f"HTTP group {index} did not execute every selected test with zero skips/failures")
            if traffic["requests"] <= before:
                raise RuntimeError(f"HTTP group {index} produced no actual Postman request events")
            executed.extend(nodes)
            report["groups"].append({"nodes": nodes, "passed": len(cases), "skipped": 0,
                                     "request_events": traffic["requests"] - before})
            print(json.dumps({"registry": domain, "http_group": index, "passed": len(cases), "skipped": 0}), flush=True)
        if len(executed) != 19 or len({node.rsplit("::", 1)[1] for node in executed}) != 13:
            raise RuntimeError("HTTP selection drifted from 19 executions / 13 distinct behaviors")
        if traffic["requests"] < 20 or not {"GET", "POST"}.issubset(traffic["methods"]):
            raise RuntimeError("Signed dependency traffic was not exercised")
        report["passed"] = len(executed)
        report["skipped"] = 0
        report["verification_complete"] = True
    finally:
        cleanup_errors = []
        if simulation:
            try:
                if simulation.poll() is None:
                    os.killpg(simulation.pid, signal.SIGTERM)
                simulation.wait(timeout=15)
            except (OSError, subprocess.SubprocessError) as exc:
                cleanup_errors.append(str(exc))
                if simulation.poll() is None:
                    os.killpg(simulation.pid, signal.SIGKILL)
                    simulation.wait(timeout=5)
        for ident in reversed(owned):
            try:
                actual = run("docker", "inspect", ident, "--format", '{{.Id}} {{index .Config.Labels "coss-refactor.owner"}}')
                if actual != f"{ident} {owner}":
                    raise RuntimeError("Owned container identity/label mismatch; refusing removal")
                run("docker", "rm", "--force", ident)
            except (RuntimeError, subprocess.SubprocessError, OSError) as exc:
                cleanup_errors.append(str(exc))
        report["cleanup_complete"] = not cleanup_errors
        report["verification_complete"] &= not cleanup_errors
        (evidence / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        if cleanup_errors:
            raise RuntimeError("Exact owned resource cleanup failed: " + "; ".join(cleanup_errors))
