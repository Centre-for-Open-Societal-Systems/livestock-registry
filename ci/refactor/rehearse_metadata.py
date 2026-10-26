"""Run one registry's metadata source through native DDL in a disposable DB."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import re
import time
import os
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]

def main(domain, pipeline=False):
    portable = (ROOT / f"{domain}-extension").is_dir()
    repo = ROOT if portable else ROOT / f"OAN/worktrees/{domain}-registry/develop-refactor"
    probes = ROOT / "ci/refactor" if portable else ROOT / "tools/registry_refactor"
    output = repo / "ci-output/refactor/new-dev"
    output.mkdir(parents=True, exist_ok=True)
    # Every bind-mounted writer uses the host identity; never chown shared
    # repository trees or alter the database container's native user.
    writer_user = ["--user", f"{os.getuid()}:{os.getgid()}"] if hasattr(os, "getuid") else []
    network = "coss-refactor-metadata-" + domain
    database = network + "-db"
    created_network = created_database = False
    network_id = database_id = None
    def run(*args):
        result = subprocess.run(args,capture_output=True,text=True,encoding="utf-8",errors="replace")
        if result.returncode:
            raise RuntimeError(result.stderr[-1800:])
        return result
    try:
        network_id = run("docker","network","create","--label","coss-refactor.disposable=metadata",network).stdout.strip()
        created_network = True
        database_id = run("docker","run","--detach","--memory=256m","--name",database,"--network",network,"--label","coss-refactor.disposable=metadata",
            "-e","POSTGRES_HOST_AUTH_METHOD=trust","-e","POSTGRES_DB=refactor_metadata","postgres:15-alpine").stdout.strip()
        created_database = True
        for _ in range(40):
            ready = subprocess.run(["docker","exec",database,"pg_isready","-h","127.0.0.1","-U","postgres"],capture_output=True)
            if ready.returncode == 0:
                break
            time.sleep(0.25)
        else:
            raise RuntimeError("Disposable database did not become ready")
        def probe(mode):
            result = run("docker","run","--rm",*writer_user,"--memory=768m","--network",network,"--entrypoint","python",
                "-v",f"{repo.as_posix()}:/work","-v",f"{probes.as_posix()}:/probe:ro",
                os.environ.get("COSS_REFACTOR_TEST_IMAGE","oan/farmer-reference-tests:rc557"),"/probe/metadata_probe.py","/work",domain,mode)
            print(result.stdout.splitlines()[-1],flush=True)
        probe("ddl")
        package = repo / f"{domain}-extension/src/openg2p_registry_{domain}_extension"
        files = sorted((package / "meta_data").rglob("*.sql"))
        steps = []
        for attempt in (1,2):
            for path in files:
                # Use native psql parsing/autocommit/ON_ERROR_STOP behavior,
                # preserving literal percent signs and DO/dollar-quoted blocks.
                raw = path.read_bytes()
                result = subprocess.run(["docker","exec","-i",database,"psql","-X","-U","postgres",
                    "-d","refactor_metadata","-v","ON_ERROR_STOP=0","-v","VERBOSITY=sqlstate"],
                    input=raw,capture_output=True)
                errors = re.findall(rb"ERROR:\s+([0-9A-Z]{5})",result.stderr)
                steps.append({"pass":attempt,"path":path.relative_to(repo).as_posix(),
                    "sha256":hashlib.sha256(raw).hexdigest(),"sqlstate_errors":[code.decode() for code in errors],
                    "psql_exit_code":result.returncode})
            probe(str(attempt))
        # Exercise the actual PostgreSQL JSON extraction and complete metadata
        # replay in isolated schemas. A native test silently skipping is failure.
        popup_test = repo / f"{domain}-extension/tests/test_popup_identity_metadata.py"
        if popup_test.exists():
            result = run("docker","run","--rm",*writer_user,"--memory=768m","--network",network,"--entrypoint","python",
                "-v",f"{repo.as_posix()}:/work","-w","/work",
                "-e",f"REGISTRY_EXTENSION_MODULE=openg2p_registry_{domain}_extension",
                "-e",f"PYTHONPATH=/work/{domain}-extension/src:/work/{domain}-extension/tests",
                "-e",f"FARMER_TEST_DATABASE_URL=postgresql+asyncpg://postgres@{database}/refactor_metadata",
                os.environ.get("COSS_REFACTOR_TEST_IMAGE","oan/farmer-reference-tests:rc557"),
                "-m","pytest","-q","-p","no:cacheprovider",f"{domain}-extension/tests/test_popup_identity_metadata.py",
                "--junitxml=/work/ci-output/refactor/new-dev/popup-identity.xml")
            print(result.stdout.splitlines()[-1],flush=True)
            cases = list(ET.parse(repo/"ci-output/refactor/new-dev/popup-identity.xml").getroot().iter("testcase"))
            if len(cases)<4 or any(case.find("skipped") is not None for case in cases):
                raise RuntimeError("Native popup metadata tests did not execute all required PostgreSQL cases")
        if pipeline:
            result = run("docker","run","--rm",*writer_user,"--memory=768m","--network",network,"--entrypoint","python",
                "-v",f"{repo.as_posix()}:/work","-v",f"{probes.as_posix()}:/probe:ro",
                "openg2p/openg2p-registry-celery:1.2.2-rc.557","/probe/notification_pipeline_probe.py","/work",domain)
            print(result.stdout.splitlines()[-1],flush=True)
        output = repo / "ci-output/refactor/new-dev"
        first = json.loads((output / "target-pass-1.json").read_text(encoding="utf-8"))
        second = json.loads((output / "target-pass-2.json").read_text(encoding="utf-8"))
        proof = {"registry":domain,"native_psql_semantics":True,"steps":steps,
                 "repeat_metadata_identical":first["metadata"] == second["metadata"],
                 "existing_environment_modified":False,"disposable_database_removed":True}
        (output / "seed-rehearsal.json").write_text(json.dumps(proof,indent=2)+"\n",encoding="utf-8",newline="\n")
        print(json.dumps({"registry":domain,"repeat_metadata_identical":proof["repeat_metadata_identical"],
            "files_with_errors":len([step for step in steps if step["sqlstate_errors"]])}),flush=True)
        if not proof["repeat_metadata_identical"] or any(step["sqlstate_errors"] or step["psql_exit_code"] for step in steps):
            raise RuntimeError("Metadata rehearsal failed: SQL errors or non-identical repeated configuration; inspect seed-rehearsal.json")
    finally:
        if created_database:
            owned = run("docker","inspect","--format",'{{.Id}} {{index .Config.Labels "coss-refactor.disposable"}}',database).stdout.strip()
            if owned != database_id + " metadata":
                raise RuntimeError("Disposable database identity changed; refusing cleanup")
            run("docker","rm","--force",database)
        if created_network:
            owned = run("docker","network","inspect","--format",'{{.Id}} {{index .Labels "coss-refactor.disposable"}}',network).stdout.strip()
            if owned != network_id + " metadata":
                raise RuntimeError("Disposable network identity changed; refusing cleanup")
            run("docker","network","rm",network)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("domain",choices=("cropsown","livestock"))
    parser.add_argument("--pipeline",action="store_true")
    args=parser.parse_args()
    main(args.domain,args.pipeline)
