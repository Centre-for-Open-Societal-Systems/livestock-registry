"""Approved identity mirrors through native domain hooks, in their transaction.

The complete profile stays in the local Farmer reference. Only existing domain
identity/display columns and the farmer's personal details (the record's first tab)
are mirrored, when the record is written and again when a change to the Farmer is
approved here (refresh_linked_records); plot/holding geography and business fields
are owned by the domain. This service never discovers or creates a relationship
from a mutable UID, a matching name, or a sibling submission.
"""
import logging

from sqlalchemy import select
from .profile import FarmerReferenceError, reference_identity, model_identity, normalize_farmer_id

_logger = logging.getLogger("oan-farmer-reference-projection")


async def _approved_farmer(session, farmer_model, reference_id):
    if not isinstance(reference_id, str) or not reference_id.strip():
        raise FarmerReferenceError("FARMER_REFERENCE_APPROVED_DEPENDENCY_REQUIRED")
    # Flush pending native approval fields before re-reading. The caller owns
    # commit/rollback; no nested independent commit may expose partial projection.
    await session.flush()
    farmer = (await session.execute(
        select(farmer_model).where(farmer_model.internal_record_id == reference_id)
        .with_for_update().execution_options(populate_existing=True)
    )).scalar_one_or_none()
    if (farmer is None or farmer.record_status != "ACTIVE" or
            not farmer.last_approved_at or not farmer.last_approved_by):
        raise FarmerReferenceError("FARMER_REFERENCE_APPROVED_DEPENDENCY_REQUIRED")
    reference_identity(model_identity(farmer))
    return farmer


def _mirror(domain_row, farmer):
    if domain_row.farmer_uuid != farmer.internal_record_id:
        raise FarmerReferenceError("FARMER_REFERENCE_LINK_MISMATCH")
    farmer_id, uid = reference_identity(model_identity(farmer))
    if domain_row.farmer_id not in (None, ""):
        # A UID rotation on the same stable reference is allowed. A different
        # Farmer ID is an identity correction and cannot be silently relinked.
        existing_id = normalize_farmer_id(domain_row.farmer_id)
        if existing_id != farmer_id:
            raise FarmerReferenceError("FARMER_REFERENCE_LINK_IDENTITY_MISMATCH")
    parts = (farmer.first_name, farmer.middle_name, farmer.last_name)
    if any(value is not None and not isinstance(value, str) for value in parts):
        raise FarmerReferenceError("FARMER_REFERENCE_INVALID_PROFILE_VALUE")
    name = " ".join(value.strip() for value in parts if value and value.strip()) or None
    proposed = {"farmer_id": farmer_id, "fayda_fan_id": farmer.fayda_fan_id,
                "link_foundational_id": uid, "farmer_name": name}
    if hasattr(domain_row, "farmer_reference_status"):
        proposed["farmer_reference_status"] = "Farmer reference linked"
    fin = getattr(farmer, "fayda_fin", None)
    if fin:
        proposed["fayda_fin"] = fin
    changed = any(getattr(domain_row, key) != value for key, value in proposed.items())
    for key, value in proposed.items():
        setattr(domain_row, key, value)
    changed = _mirror_profile(domain_row, farmer) or changed
    if changed:
        domain_row.search_text = domain_row.get_search_text_fields()
        domain_row.record_name = domain_row.get_record_name_fields()
    return int(changed)


# The farmer's personal details, from the approved Farmer, shown read-only on the
# record's first tab (zz-oan/96_record_farmer_profile.sql). Farmer column -> record column.
MIRRORED_PROFILE_FIELDS = {
    "gender": "farmer_gender", "date_of_birth": "farmer_date_of_birth",
    "mobile_number": "farmer_mobile_number", "marital_status": "farmer_marital_status",
    "education_level": "farmer_education_level", "language_spoken": "farmer_language_spoken",
    "disabled": "farmer_disabled", "disability_type": "farmer_disability_type",
}


def _mirror_profile(domain_row, farmer) -> bool:
    """Copy the approved Farmer's personal details onto a record that has the columns.

    Field by field, only where the Farmer has a value: a Farmer without one never
    clears what the record already holds.
    """
    changed = False
    for source, target in MIRRORED_PROFILE_FIELDS.items():
        if not hasattr(domain_row, target):
            continue
        value = getattr(farmer, source, None)
        if value is None or value == "":
            continue
        if getattr(domain_row, target) != value:
            setattr(domain_row, target, value)
            changed = True
    return changed


async def refresh_linked_records(session, farmer, domain_model) -> int:
    """After a change to a Farmer is approved here, copy it onto every active record
    that names this Farmer (farmer_uuid), in the approval's transaction.

    Only approved records (record_status ACTIVE) are rewritten: drafts are intake
    submissions, which take the Farmer when they are approved. A record whose Farmer
    ID no longer matches is left as it is and logged; the change to the Farmer is
    still approved.
    """
    rows = (await session.execute(
        select(domain_model).where(domain_model.farmer_uuid == farmer.internal_record_id,
                                   domain_model.record_status == "ACTIVE")
        .with_for_update()
    )).scalars().all()
    changed = 0
    for row in rows:
        try:
            changed += _mirror(row, farmer)
        except FarmerReferenceError as error:
            _logger.warning("record %s not refreshed from Farmer %s: %s",
                            row.internal_record_id, farmer.internal_record_id, error)
    await session.flush()
    return changed


async def backfill_profiles(session, farmer_model, domain_model) -> tuple[int, int]:
    """Once, for records written before the personal details came from the Farmer: mirror
    each active record from its approved Farmer, as refresh_linked_records does (see
    profile_backfill.py). A Farmer without a value leaves the record's value as it is;
    a record under another Farmer ID is logged and left."""
    rows = (await session.execute(select(domain_model).where(
        domain_model.record_status == "ACTIVE", domain_model.farmer_uuid.is_not(None)))).scalars().all()
    changed = 0
    for row in rows:
        farmer = await session.get(farmer_model, row.farmer_uuid)
        if farmer is None or farmer.record_status != "ACTIVE":
            continue
        try:
            changed += _mirror(row, farmer)
        except FarmerReferenceError as error:
            _logger.warning("record %s not refreshed from Farmer %s: %s",
                            row.internal_record_id, farmer.internal_record_id, error)
    await session.flush()
    return len(rows), changed


async def refresh_domain_on_ingest(session, farmer_model, domain_row):
    """Block activation without the already approved stable local dependency.

    The native ingester invokes post_ingest before committing. A failure rolls
    back its new live row. Onboarding must supply farmer_uuid; a reviewed link
    migration must handle old records rather than this hook choosing an owner.
    """
    farmer = await _approved_farmer(session, farmer_model, domain_row.farmer_uuid)
    changed = _mirror(domain_row, farmer)
    await session.flush()
    return changed
