"""Applies the audit-log-retention scheduling patch to the base image's
installed openg2p_registry_celery_beat at build time — G2R-135's "7-year
retention period" requirement.

Same technique as docker/staff-api/core-patches/apply_patches.py and the same
reason: celery-beat's task registry and beat_schedule are both hardcoded in
its own installed package, with no extension hook for a domain package to
add a scheduled task of its own — so this is a minimal, exact-match patch
rather than a wholesale file replacement, applied at every build so it
survives rebuilds instead of being silently lost.

Run at Docker build time only (see docker/celery/Dockerfile).
"""

BASE = "/usr/local/lib/python3.12/site-packages/openg2p_registry_celery_beat"


def apply(path, old, new, label):
    with open(path) as f:
        content = f.read()
    n = content.count(old)
    assert n == 1, f"{label}: expected 1 match in {path}, found {n}"
    content = content.replace(old, new)
    with open(path, "w") as f:
        f.write(content)
    print(f"OK: {label}")


# ─── Register the livestock extension's audit-log-retention task alongside
# celery-beat's own producers, so `include=["openg2p_registry_celery_beat.tasks"]`
# picks it up too.
apply(
    f"{BASE}/tasks/__init__.py",
    '''from .import_file_process_beat_producer import import_file_process_beat_producer''',
    '''from .import_file_process_beat_producer import import_file_process_beat_producer
from openg2p_registry_livestock_extension.tasks.audit_log_retention_beat_producer import (
    audit_log_retention_beat_producer,
)''',
    "tasks/__init__.py: register audit_log_retention_beat_producer",
)

# ─── Schedule it — once a day. A housekeeping job, not high-frequency data
# pipeline work like the producers above it, so a fixed interval rather than
# a new Settings field is enough here.
apply(
    f"{BASE}/app.py",
    '''    "import_file_process_beat_producer": {
        "task": "import_file_process_beat_producer",
        "schedule": (
            _config.import_file_process_beat_producer_frequency
            or _config.default_beat_producer_frequency
        ),
    },
}
celery_app.conf.timezone = "UTC"''',
    '''    "import_file_process_beat_producer": {
        "task": "import_file_process_beat_producer",
        "schedule": (
            _config.import_file_process_beat_producer_frequency
            or _config.default_beat_producer_frequency
        ),
    },
    "audit_log_retention_beat_producer": {
        "task": "audit_log_retention_beat_producer",
        "schedule": 86400.0,  # once a day
    },
}
celery_app.conf.timezone = "UTC"''',
    "app.py: schedule audit_log_retention_beat_producer daily",
)

print("ALL PATCHES APPLIED")
