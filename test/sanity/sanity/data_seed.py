"""Idempotent injection of the sanity livestock record into the registry database.

Why SQL and not an API:
  * every staff-portal-api register write is a **change request** — using it to
    build a fixture would mean creating and approving a CR before the DCI test
    could run, entangling two tests;
  * the record must exist in a known, ACTIVE, already-approved state so the DCI
    search is deterministic.

Why the test data is injected at all rather than reusing seeded sample data: the
livestock sample records are only present when the sample-data set is applied,
which a production install does not do — the e2e must not depend on them.

**`search_text` is written explicitly.** On the ORM it is auto-populated by
SQLAlchemy event listeners, which do NOT fire for raw SQL. db-seed's
load_sample_data.py has the same constraint and does the same thing. The DCI
search is `search_text ILIKE '%<text>%'`, so this column is what makes the
injected record findable.
"""

from . import fixtures

_COLUMNS = [
    "internal_record_id", "functional_record_id",
    "record_name", "created_by", "created_at",
    "last_approved_at", "last_approved_by",
    "search_text", "record_status",
    "farmer_id", "fayda_fan_id", "farmer_name", "oan_id", "status",
    "state", "source_system", "surveyor_name",
]

# Re-runnable: a second install/upgrade updates the row rather than colliding on
# the primary key, and resets the change-request field (surveyor_name) and
# search_text so every run starts from a known state.
_UPSERT = f"""
INSERT INTO "public"."g2p_register_livestocks" ({", ".join(f'"{c}"' for c in _COLUMNS)})
VALUES ({", ".join(["%s"] * len(_COLUMNS))})
ON CONFLICT ("internal_record_id") DO UPDATE SET
    "search_text"          = EXCLUDED."search_text",
    "record_status"        = EXCLUDED."record_status",
    "surveyor_name"        = EXCLUDED."surveyor_name",
    "farmer_name"          = EXCLUDED."farmer_name",
    "farmer_id"            = EXCLUDED."farmer_id",
    "fayda_fan_id"         = EXCLUDED."fayda_fan_id",
    "oan_id"               = EXCLUDED."oan_id",
    "status"               = EXCLUDED."status",
    "state"                = EXCLUDED."state",
    "source_system"        = EXCLUDED."source_system";
"""

_CREATED_AT = "2026-01-01 00:00:00"


def _row():
    f = fixtures.FARMER
    record_name = f"{f['farmer_name']} {f['oan_id']}"
    # The marker must be inside search_text — that is the only column the DCI
    # search matches on.
    search_text = " ".join([
        fixtures.SEARCH_MARKER,
        fixtures.FARMER_FUNCTIONAL_ID,
        f["oan_id"],
        f["farmer_name"],
        f["farmer_id"],
        f["fayda_fan_id"],
        f["status"],
        f["state"],
        f["source_system"],
    ])
    return (
        fixtures.FARMER_INTERNAL_ID, fixtures.FARMER_FUNCTIONAL_ID,
        record_name, fixtures.CREATED_BY, _CREATED_AT,
        _CREATED_AT, fixtures.CREATED_BY,
        search_text, "ACTIVE",
        f["farmer_id"], f["fayda_fan_id"], f["farmer_name"],
        f["oan_id"], f["status"], f["state"],
        f["source_system"], fixtures.CR_VALUE_INITIAL,
    )


def ensure_seeded(cfg) -> str:
    """Insert (or reset) the sanity livestock record. Returns "seeded"."""
    from . import db

    db.execute(cfg.registry_dsn, _UPSERT, _row())
    return "seeded"


def main() -> int:
    """CLI entrypoint (`python -m sanity.data_seed`) for the deploy-time Job.
    Idempotent; exits 0 on success or benign skip, non-zero on unexpected error."""
    from .config import Config

    cfg = Config.from_env()
    if not cfg.registry_dsn:
        print("[data-seed] registry DB not configured — nothing to seed; skipping")
        return 0
    try:
        status = ensure_seeded(cfg)
    except Exception as exc:  # noqa: BLE001
        print(f"[data-seed] FAILED to seed livestock '{fixtures.FARMER_FUNCTIONAL_ID}': {exc}")
        return 1
    print(f"[data-seed] livestock '{fixtures.FARMER_FUNCTIONAL_ID}': {status}")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
