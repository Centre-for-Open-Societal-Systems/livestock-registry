"""Validate an isolated source port without running a registry or touching data."""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path


def verify(repo: Path, domain: str) -> dict:
    source = repo / f"{domain}-extension/src/openg2p_registry_{domain}_extension"
    status = json.loads((repo / "docs/refactor/STATUS.json").read_text(encoding="utf-8"))
    errors = []
    assert status["promotion_ready"] is False
    assert status["blockers"]
    count = 0
    for path in source.rglob("*.py"):
        body = path.read_text(encoding="utf-8-sig")
        tree = ast.parse(body, filename=str(path))
        count += 1
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Attribute) and isinstance(node.value, (ast.Name, ast.Lambda)):
                        owner = ast.unparse(target.value)
                        if owner.startswith("G2P") and ("Service" in owner or "Worker" in owner):
                            errors.append(f"{path}:{node.lineno}: runtime method replacement")
        if "sys.meta_path" in body or "setup_intake_hooks" in body or "from .worker_hooks" in body:
            errors.append(f"{path}: legacy import/worker patch")
        if "db_engine_master_data" in body or "SELECT display_name FROM g2p_geo_level_values" in body:
            errors.append(f"{path}: direct Master Data database read")
    for role in ("staff-api", "partner-api", "celery"):
        text = (repo / f"docker/{role}/Dockerfile").read_text(encoding="utf-8")
        if f"ENV REGISTRY_EXTENSION_MODULE=openg2p_registry_{domain}_extension" not in text:
            errors.append(f"{role}: wrong extension module")
        if re.search(r"core-patches|site-packages|COPY.*patch|apply_patches", text):
            errors.append(f"{role}: platform patch")
    pins = set()
    for path in (repo / "docker").glob("*/Dockerfile"):
        pin = re.search(r"^ARG RP_VERSION=(\S+)", path.read_text(encoding="utf-8"), re.M)
        if pin:
            pins.add(pin[1])
    profile = json.loads((repo / "ci/deploy/oan-chart.json").read_text(encoding="utf-8"))
    pin = profile["registry"]
    pins.add(pin["platformVersion"])
    if not re.fullmatch(r"https://raw\.githubusercontent\.com/Centre-for-Open-Societal-Systems/oan-helm/[0-9a-f]{40}/repository/",pin["repository"]):
        errors.append("central chart commit is not immutable")
    if pin["promotionReady"] is not False or profile["dashboard"]["promotionReady"] is not False:
        errors.append("incomplete refactor deployment enabled")
    for name in ("helm", "openg2p-connector-service", "openg2p-connector-ui"):
        if any((repo / name).rglob("Chart.yaml")) or (repo / name / "Dockerfile").exists():
            errors.append("retired vendored source remains: " + name)
    if pins != {"1.2.2-rc.557"}:
        errors.append(f"split platform pins: {pins}")
    if (repo / "farmer-extension").exists():
        errors.append("upstream Farmer example package remains")
    if any((repo / f"docker/{role}/core-patches").exists() for role in ("staff-api", "partner-api", "celery")):
        errors.append("platform patches remain")
    if any((repo / "docker/staff-ui").rglob("patch-*.js")):
        errors.append("compiled UI patches remain")
    if (source / "register_domain/factory").exists():
        errors.append("replacement domain factory remains")
    if (source / "register_domain/controllers/g2p_animal_bulk_import_controller.py").exists():
        errors.append("custom bulk import remains")
    awe = source / "awe_meta_data"
    if awe.exists():
        supported = {"10_approval_policy.sql", "20_approval_stage.sql", "30_approver_rule.sql"}
        files = {path.name for path in awe.iterdir() if path.is_file()}
        if files != supported:
            errors.append("Unreviewed or legacy approval seed files remain")
        else:
            stage = (awe / "20_approval_stage.sql").read_text(encoding="utf-8")
            rule = (awe / "30_approver_rule.sql").read_text(encoding="utf-8")
            if "'block'" not in stage or "'all'" not in stage or "'user'" not in rule or "alex.carter" not in rule or "nina.patel" not in rule or "geo_woreda_approver_ids" in rule:
                errors.append("OpenG2P default approvals must use sequential all/block user stages")
    preflight = (repo / "ci/refactor/seed-preflight.sh").read_text(encoding="utf-8")
    if not preflight.rstrip().endswith("exit 1"):
        errors.append("incomplete port can seed an environment")
    if not re.fullmatch(r"[0-9a-f]{64}",pin["sha256"]):
        errors.append("missing immutable central chart checksum")
    # No branch-specific auto-deployment may be introduced by curation.
    jenkins = (repo / "Jenkinsfile").read_text(encoding="utf-8")
    if "branch 'develop-refactor'" in jenkins or 'branch "develop-refactor"' in jenkins:
        errors.append("refactor deploy enabled")
    if errors:
        raise ValueError("\n".join(errors))
    return {"domain": domain, "python_files_parsed": count, "platform_pins": sorted(pins), "promotion_ready": False, "source_checks": "PASS"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("repo", type=Path)
    parser.add_argument("domain", choices=("cropsown", "livestock"))
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.repo.resolve(), args.domain), indent=2))
    except (ValueError, AssertionError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
