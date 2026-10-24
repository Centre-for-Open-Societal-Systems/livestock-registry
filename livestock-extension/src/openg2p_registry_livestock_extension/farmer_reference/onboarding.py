"""Transactional Farmer dependency orchestration, independent of delivery channel.

The caller supplies its active native transaction. No commits, network calls,
trusted shell Farmers or worker replacements occur here. Native CR construction
is an injected session-aware service; AWE delivery uses the committed outbox.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha256
import json
from uuid import uuid4

from sqlalchemy import select, text

from .lookup import VerifiedFarmer
from .models import FarmerReference, FarmerReferenceRequest, FarmerSubmissionDependency, FarmerWorkflowOutbox
from .profile import FarmerReferenceError, identity_pair, PROFILE_FIELDS


def _json_profile(profile: dict) -> dict:
    return json.loads(json.dumps(profile, default=lambda value: value.isoformat() if isinstance(value, (date, datetime)) else _bad_value()))


def _bad_value():
    raise FarmerReferenceError("FARMER_REFERENCE_INVALID_PROFILE_VALUE")


class OnboardingService:
    def __init__(self, farmer_model, create_native_cr):
        self.farmer_model = farmer_model
        self.create_native_cr = create_native_cr

    async def _lock_source(self, session, source_system: str, farmer_id: str):
        # Serializes the absent-row case as well as subsequent reference updates.
        # Locks belong to the caller's transaction and disappear on rollback.
        if session.bind.dialect.name == "postgresql":
            key = int.from_bytes(sha256((source_system + "\0" + farmer_id).encode()).digest()[:8], "big", signed=True)
            await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
        elif session.bind.dialect.name != "sqlite":
            raise FarmerReferenceError("FARMER_REFERENCE_UNSUPPORTED_DATABASE")

    def _validate_snapshot(self, source: VerifiedFarmer):
        # Only an internal verified lookup result enters here; no API trust flag.
        if not isinstance(source, VerifiedFarmer):
            raise FarmerReferenceError("FARMER_REFERENCE_VERIFIED_LOOKUP_REQUIRED")
        if (not source.source_system or not source.source_record_id or
                type(source.source_version) is not int or source.source_version <= 0 or
                not source.response_digest or set(source.profile) - PROFILE_FIELDS):
            raise FarmerReferenceError("FARMER_REFERENCE_INVALID_VERIFIED_SNAPSHOT")
        age = (datetime.now(timezone.utc) - source.fetched_at).total_seconds()
        if not -30 <= age <= 300:
            raise FarmerReferenceError("FARMER_REFERENCE_LOOKUP_EXPIRED")
        return identity_pair(source.profile.get("farmer_id"), source.profile.get("fayda_fan_id"))

    async def _reference(self, session, source: VerifiedFarmer, *, allow_create: bool):
        farmer_id, uid = self._validate_snapshot(source)
        await self._lock_source(session, source.source_system, farmer_id)
        reference = (await session.execute(select(FarmerReference).where(
            FarmerReference.source_system == source.source_system,
            FarmerReference.farmer_id == farmer_id).with_for_update())).scalar_one_or_none()
        if reference:
            if reference.source_record_id != source.source_record_id:
                raise FarmerReferenceError("FARMER_REFERENCE_SOURCE_ID_MISMATCH")
            if reference.state != "APPROVED" and reference.uid != uid:
                raise FarmerReferenceError("FARMER_REFERENCE_PENDING_IDENTITY_CHANGED")
            return reference
        if not allow_create:
            # Kafka updates never onboard an unreferenced central Farmer.
            return None
        # Existing approved references can be adopted only by this verified exact
        # pair. Never pick an arbitrary row when identities are ambiguous.
        Farmer = self.farmer_model
        rows = (await session.execute(select(Farmer).where(
            (Farmer.farmer_id == farmer_id) | (Farmer.fayda_fan_id == uid)).with_for_update())).scalars().all()
        local_id = None
        if rows:
            if (len(rows) != 1 or identity_pair(rows[0].farmer_id, rows[0].fayda_fan_id) != (farmer_id, uid) or
                    rows[0].record_status != "ACTIVE" or not rows[0].last_approved_at or not rows[0].last_approved_by):
                raise FarmerReferenceError("FARMER_REFERENCE_EXISTING_IDENTITY_AMBIGUOUS")
            local_id = rows[0].internal_record_id
        reference = FarmerReference(reference_id=str(uuid4()), source_system=source.source_system,
            source_record_id=source.source_record_id, farmer_id=farmer_id, uid=uid,
            local_farmer_id=local_id or str(uuid4()), applied_version=0,
            state="APPROVED" if local_id else "PENDING")
        # Adoption does not assert an applied source version or overwrite an
        # already approved local profile. The next notification creates UPDATE.
        session.add(reference)
        await session.flush()
        return reference

    async def ensure_dependency(self, session, submission_id: str, source: VerifiedFarmer, *, requester="system"):
        reference = await self._reference(session, source, allow_create=True)
        if reference.state == "REJECTED":
            raise FarmerReferenceError("FARMER_REFERENCE_DEPENDENCY_REJECTED")
        if reference.uid != source.profile["fayda_fan_id"]:
            raise FarmerReferenceError("FARMER_REFERENCE_LOCAL_IDENTITY_UPDATE_REQUIRED")
        existing = await session.get(FarmerSubmissionDependency, submission_id)
        if existing:
            if existing.reference_id != reference.reference_id:
                raise FarmerReferenceError("FARMER_REFERENCE_SUBMISSION_IDENTITY_CHANGED")
            return reference
        if reference.state != "APPROVED" and not reference.pending_add_request_id:
            request = await self._create_request(session, reference, source, "ADD", requester=requester)
            reference.pending_add_request_id = request.request_id
        session.add(FarmerSubmissionDependency(submission_id=submission_id, reference_id=reference.reference_id,
            farmer_request_id=reference.pending_add_request_id))
        await session.flush()
        return reference

    async def _create_request(self, session, reference, source, action, *, requester="system"):
        profile = _json_profile(dict(source.profile))
        native_cr = await self.create_native_cr(session, reference.local_farmer_id, profile, action, created_by=requester)
        request = FarmerReferenceRequest(request_id=str(uuid4()), reference_id=reference.reference_id,
            native_cr_id=native_cr.change_request_id, source_version=source.source_version,
            action=action, state="PENDING", profile=profile, response_digest=source.response_digest)
        session.add(request)
        session.add(FarmerWorkflowOutbox(native_cr_id=native_cr.change_request_id, request_id=request.request_id,
            state="PENDING", attempts=0))
        await session.flush()
        return request

    async def queue_current_update(self, session, source: VerifiedFarmer):
        reference = await self._reference(session, source, allow_create=False)
        if not reference or reference.state != "APPROVED" or source.source_version <= reference.applied_version:
            return None
        existing = (await session.execute(select(FarmerReferenceRequest).where(
            FarmerReferenceRequest.reference_id == reference.reference_id,
            FarmerReferenceRequest.source_version == source.source_version,
            FarmerReferenceRequest.action == "UPDATE"))).scalar_one_or_none()
        if existing:
            # Rejected versions are also delivery-idempotent; no approval replay.
            if existing.profile != _json_profile(dict(source.profile)):
                raise FarmerReferenceError("FARMER_REFERENCE_SOURCE_VERSION_CONFLICT")
            return existing
        return await self._create_request(session, reference, source, "UPDATE")

    async def require_approved_dependency(self, session, submission_id: str):
        dependency = await session.get(FarmerSubmissionDependency, submission_id)
        if not dependency:
            raise FarmerReferenceError("FARMER_REFERENCE_DEPENDENCY_REQUIRED")
        reference = await session.get(FarmerReference, dependency.reference_id)
        if reference.state != "APPROVED":
            code = "REJECTED" if reference.state == "REJECTED" else "PENDING"
            raise FarmerReferenceError("FARMER_REFERENCE_DEPENDENCY_" + code)
        farmer = await session.get(self.farmer_model, reference.local_farmer_id, with_for_update=True)
        if (not farmer or farmer.record_status != "ACTIVE" or
                not farmer.last_approved_at or not farmer.last_approved_by):
            raise FarmerReferenceError("FARMER_REFERENCE_APPROVED_LOCAL_REQUIRED")
        return farmer

    async def link_approved_dependency(self, session, submission_id: str, local_id: str, farmer_id: str, uid: str):
        """Later domain intake reuses its existing approved stable reference.

        The caller must derive local_id from the already approved domain row,
        never from a client-supplied link. No new onboarding or source lookup.
        """
        reference = (await session.execute(select(FarmerReference).where(
            FarmerReference.local_farmer_id == local_id).with_for_update())).scalar_one_or_none()
        if not reference or reference.state != "APPROVED":
            raise FarmerReferenceError("FARMER_REFERENCE_APPROVED_LOCAL_REQUIRED")
        if identity_pair(farmer_id, uid) != (reference.farmer_id, reference.uid):
            raise FarmerReferenceError("FARMER_REFERENCE_SUBMISSION_IDENTITY_CHANGED")
        existing = await session.get(FarmerSubmissionDependency, submission_id)
        if existing and existing.reference_id != reference.reference_id:
            raise FarmerReferenceError("FARMER_REFERENCE_SUBMISSION_IDENTITY_CHANGED")
        if not existing:
            session.add(FarmerSubmissionDependency(submission_id=submission_id, reference_id=reference.reference_id))
            await session.flush()
        await self.require_approved_dependency(session, submission_id)
        return reference

    async def approval_guard(self, session, native_cr_id: str):
        request = (await session.execute(select(FarmerReferenceRequest).where(
            FarmerReferenceRequest.native_cr_id == native_cr_id))).scalar_one_or_none()
        if not request:
            raise FarmerReferenceError("FARMER_REFERENCE_MANAGED_REQUEST_REQUIRED")
        reference = await session.get(FarmerReference, request.reference_id, with_for_update=True)
        await session.refresh(request)
        if request.state != "PENDING" or request.source_version <= reference.applied_version:
            raise FarmerReferenceError("FARMER_REFERENCE_STALE_SOURCE_VERSION")
        if request.action == "ADD" and reference.state != "PENDING":
            raise FarmerReferenceError("FARMER_REFERENCE_ADD_ALREADY_RESOLVED")
        if request.action == "UPDATE" and reference.state != "APPROVED":
            raise FarmerReferenceError("FARMER_REFERENCE_APPROVED_LOCAL_REQUIRED")
        return reference, request

    async def record_decision(self, session, native_cr_id: str, approved: bool):
        if approved:
            reference, request = await self.approval_guard(session, native_cr_id)
        else:
            # A stale pending UPDATE can still be rejected/closed. It must not
            # block newer native requests or roll back an already applied one.
            request = (await session.execute(select(FarmerReferenceRequest).where(
                FarmerReferenceRequest.native_cr_id == native_cr_id))).scalar_one_or_none()
            if not request:
                raise FarmerReferenceError("FARMER_REFERENCE_MANAGED_REQUEST_REQUIRED")
            reference = await session.get(FarmerReference, request.reference_id, with_for_update=True)
            await session.refresh(request)
            if request.state != "PENDING":
                if request.state == "REJECTED":
                    return
                raise FarmerReferenceError("FARMER_REFERENCE_REQUEST_ALREADY_RESOLVED")
        request.state = "APPROVED" if approved else "REJECTED"
        if approved:
            farmer = await session.get(self.farmer_model, reference.local_farmer_id)
            if (not farmer or farmer.record_status != "ACTIVE" or
                    identity_pair(farmer.farmer_id, farmer.fayda_fan_id) !=
                    identity_pair(request.profile["farmer_id"], request.profile["fayda_fan_id"])):
                raise FarmerReferenceError("FARMER_REFERENCE_APPROVED_LOCAL_REQUIRED")
            reference.uid = request.profile["fayda_fan_id"]
            reference.applied_version = request.source_version
            reference.state = "APPROVED"
        elif request.action == "ADD":
            reference.state = "REJECTED"
        await session.flush()
