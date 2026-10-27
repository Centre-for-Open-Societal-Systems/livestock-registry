"""Inspect installed platform code; never import workers or connect to services."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path


def package_path(name):
    return Path(importlib.util.find_spec(name).origin).parent


def evidence(path, predicate):
    raw = path.read_bytes()
    tree = ast.parse(raw)
    matches = [{"line": node.lineno, "symbol": getattr(node, "name", None)} for node in ast.walk(tree) if predicate(node)]
    return {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(), "matches": matches}


worker = package_path("openg2p_registry_celery_worker")
beat = package_path("openg2p_registry_celery_beat")
core = package_path("openg2p_registry_core")
result = {
    "worker_initializer": evidence(worker / "app.py", lambda n: isinstance(n, ast.ClassDef) and n.name == "Initializer"),
    "worker_cr_creator": evidence(core / "services/g2p_change_request_worker_service.py", lambda n: isinstance(n, ast.AsyncFunctionDef) and n.name == "create_change_request"),
    "worker_awe_calls": evidence(core / "services/g2p_change_request_worker_service.py", lambda n: isinstance(n, ast.Call) and "start_change_request_workflow" in ast.unparse(n.func)),
    "beat_extension_initializer_imports": evidence(beat / "app.py", lambda n: isinstance(n, ast.ImportFrom) and "openg2p_registry_extensions" in (n.module or "")),
    "worker_extension_initializer_imports": evidence(worker / "app.py", lambda n: isinstance(n, ast.ImportFrom) and "openg2p_registry_extensions" in (n.module or "")),
    "session_aware_intake_validation": evidence(core / "services/intake_form_data_service.py", lambda n: isinstance(n, ast.Call) and "validate_domain_attributes" in ast.unparse(n.func) and any(k.arg == "session" for k in n.keywords)),
}
print(json.dumps(result, indent=2))
