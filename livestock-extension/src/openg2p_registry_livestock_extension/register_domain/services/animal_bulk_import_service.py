"""Bulk Animal import from a CSV spreadsheet.

"Upload a spreadsheet, system reads every row and creates/updates matching
animal records automatically" — the platform already has a generic,
heavyweight bulk-file-ingest pipeline (import_file_process_worker.py +
the DCI data-model/semantic-pattern/template machinery in
meta_data/registry-inbound-message-rules/), but that pipeline is built for
whole-submission-shaped partner messages (a full Farmer+Livestock+Animal+...
payload per row, DCI-wrapped), not a flat "just the animals" spreadsheet —
wiring a new spreadsheet shape through it would mean adding a new semantic
pattern + jinja2 template to that framework, which is a much larger, riskier
change for what's fundamentally a simple upsert. This module does the same
job directly and simply instead: parse a CSV, and for each row, create a new
Animal or update the matching existing one (matched by ear_tag_id under the
named Livestock record).

Expected CSV columns (header row, order doesn't matter):
    livestock_functional_record_id (required) — e.g. "LS-000000000001",
        identifies which Livestock holding the animal belongs/is added to.
    ear_tag_id       (required) — e.g. "ET0000100001". Matches an existing
        Animal row under that livestock -> UPDATE; no match -> CREATE.
    species          (required) — LIVESTOCK_SPECIES attribute value id.
    gender           (required) — MALE / FEMALE / MIXED.
    breed, date_of_birth (YYYY-MM-DD), weight, health_status,
    vaccination_status, secondary_identifier — all optional; a blank cell
    leaves an existing animal's value untouched (does not blank it out) and
    is simply omitted on a new animal.

Plain, directly-callable async function for the same reason the other new
services this session are — callable from a small on-demand script/task, and
callable directly for a same-day test without any new UI wiring.
"""

import csv

from .g2p_register_domain_service_animal import _EAR_TAG_PATTERN
import io
import logging
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select

from openg2p_registry_core.models import G2PFunctionalIdGenerationQueue

from .domain_validation_utils import _animal_models, is_blank

_logger = logging.getLogger("g2p-bulk-import")

ANIMAL_REGISTER_ID = "041a9f79-2142-548a-a15b-a4c76fc9f6f7"

_REQUIRED_COLUMNS = ["livestock_functional_record_id", "ear_tag_id", "species", "gender"]
_OPTIONAL_COLUMNS = [
    "breed", "date_of_birth", "weight", "health_status", "vaccination_status", "secondary_identifier",
]


def _parse_date(value: str):
    value = (value or "").strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


async def import_animals_from_csv(file_bytes: bytes, actor: str, session, filename: str | None = None) -> dict:
    """Parse `file_bytes` as CSV and upsert one Animal row per data row.
    Returns {"total": n, "created": n, "updated": n, "failed": n, "errors": [...]}.
    Commits nothing itself — caller controls the transaction (session.commit()),
    same as every other domain-service DB touch point in this extension.
    """
    text = file_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    missing = [col for col in _REQUIRED_COLUMNS if col not in (reader.fieldnames or [])]
    if missing:
        raise ValueError(f"CSV is missing required column(s): {', '.join(missing)}")

    from .g2p_register_domain_service_animal import G2PRegisterDomainServiceAnimal

    G2PRegisterAnimal, _ = _animal_models()
    animal_service = G2PRegisterDomainServiceAnimal()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    import importlib
    G2PRegisterLivestock = importlib.import_module(
        "openg2p_registry_extensions.register_domain.models"
    ).G2PRegisterLivestock

    result = {"total": 0, "created": 0, "updated": 0, "failed": 0, "errors": []}
    per_holding: dict[str, dict] = {}  # livestock internal_record_id -> counters for the ImportBatch audit row

    for row_number, row in enumerate(reader, start=2):  # header is row 1
        result["total"] += 1
        holding = None  # counters of the holding this row resolves to (for the audit row)
        try:
            livestock_ref = (row.get("livestock_functional_record_id") or "").strip()
            ear_tag_id = (row.get("ear_tag_id") or "").strip()
            species = (row.get("species") or "").strip()
            gender = (row.get("gender") or "").strip().upper()

            if not livestock_ref:
                raise ValueError("livestock_functional_record_id is required")

            # A savepoint per row: one bad row (a DB-level constraint error,
            # not just a plain validation ValueError above) rolls back only
            # its own work, not every row already committed to the session
            # earlier in this same file.
            async with session.begin_nested():
                livestock = (
                    await session.execute(
                        select(G2PRegisterLivestock).where(
                            G2PRegisterLivestock.functional_record_id == livestock_ref
                        )
                    )
                ).scalar()
                if not livestock:
                    raise ValueError(f"No Livestock record found with functional_record_id '{livestock_ref}'")
                holding = per_holding.setdefault(
                    livestock.internal_record_id, {"total": 0, "ok": 0, "failed": 0, "errors": []}
                )
                holding["total"] += 1

                # Field checks come after the holding is known, so a rejected
                # row is counted against its holding's audit row too.
                if not ear_tag_id or not species or not gender:
                    raise ValueError("ear_tag_id, species and gender are all required")
                ear_tag_id = ear_tag_id.upper()
                if not _EAR_TAG_PATTERN.match(ear_tag_id):
                    raise ValueError(f"ear_tag_id '{ear_tag_id}' must be ET followed by exactly 10 digits, e.g. ET0000000123")

                existing = (
                    await session.execute(
                        select(G2PRegisterAnimal).where(
                            G2PRegisterAnimal.ear_tag_id == ear_tag_id,
                            G2PRegisterAnimal.link_internal_record_id == livestock.internal_record_id,
                        )
                    )
                ).scalar()

                payload = {"ear_tag_id": ear_tag_id, "species": species, "gender": gender}
                if not is_blank(row.get("breed")):
                    payload["breed"] = row["breed"].strip()
                if not is_blank(row.get("date_of_birth")):
                    payload["date_of_birth"] = _parse_date(row["date_of_birth"])
                if not is_blank(row.get("weight")):
                    payload["weight"] = float(row["weight"])
                if not is_blank(row.get("health_status")):
                    payload["health_status"] = row["health_status"].strip().upper()
                if not is_blank(row.get("vaccination_status")):
                    payload["vaccination_status"] = row["vaccination_status"].strip().upper()
                if not is_blank(row.get("secondary_identifier")):
                    payload["secondary_identifier"] = row["secondary_identifier"].strip()

                if existing:
                    for key, value in payload.items():
                        setattr(existing, key, value)
                    existing.record_name = animal_service.construct_record_name(existing.to_dict())
                    existing.search_text = animal_service.construct_search_text(existing.to_dict())
                    result["updated"] += 1
                    holding["ok"] += 1
                else:
                    internal_id = str(uuid.uuid4())
                    animal = G2PRegisterAnimal(
                        internal_record_id=internal_id,
                        link_internal_record_id=livestock.internal_record_id,
                        record_status="ACTIVE",
                        created_by=actor,
                        created_at=now,
                        last_approved_by=actor,
                        last_approved_at=now,
                        registration_date=date.today(),
                        state="DRAFT",
                        **payload,
                    )
                    animal.record_name = animal_service.construct_record_name(payload)
                    animal.search_text = animal_service.construct_search_text(payload)
                    session.add(animal)
                    session.add(
                        G2PFunctionalIdGenerationQueue(
                            register_id=ANIMAL_REGISTER_ID,
                            internal_record_id=internal_id,
                        )
                    )
                    result["created"] += 1
                    holding["ok"] += 1

                await session.flush()
        except Exception as error:
            result["failed"] += 1
            result["errors"].append(f"Row {row_number}: {error}")
            if holding is not None:
                holding["failed"] += 1
                holding["errors"].append(f"Row {row_number}: {error}")
            _logger.warning("Bulk animal import row %d failed: %s", row_number, error)

    # One ImportBatch audit row per holding touched, so the upload shows up
    # under the holding's Imports & Audit tab like the Old System's import log.
    if per_holding:
        G2PRegisterImportBatch = importlib.import_module(
            "openg2p_registry_extensions.register_domain.models"
        ).G2PRegisterImportBatch
        stamp = now.strftime("%Y%m%d-%H%M%S")
        for index, (livestock_internal_id, counters) in enumerate(per_holding.items(), start=1):
            batch_reference = f"BULK-{stamp}-{index}"
            batch = G2PRegisterImportBatch(
                internal_record_id=str(uuid.uuid4()),
                link_internal_record_id=livestock_internal_id,
                record_status="ACTIVE",
                created_by=actor,
                created_at=now,
                last_approved_by=actor,
                last_approved_at=now,
                batch_reference=batch_reference,
                source_system="MANUAL",
                state="COMPLETED" if counters["failed"] == 0 else "FAILED",
                import_filename=filename or "upload.csv",
                total_rows=counters["total"],
                success_count=counters["ok"],
                failure_count=counters["failed"],
                conflict_count=0,
                error_log="\n".join(counters["errors"]) or None,
                processed_by=actor,
                processing_date=now,
            )
            batch.record_name = batch_reference
            batch.search_text = f"{batch_reference} {filename or ''} MANUAL".strip()
            session.add(batch)
        await session.flush()
    _logger.info(
        "Bulk animal import: %d row(s), %d created, %d updated, %d failed",
        result["total"], result["created"], result["updated"], result["failed"],
    )
    return result
