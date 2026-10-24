"""Read-only intersection of functional eligibility and resolved geo policies.

This is the extension's internal contract, not an IAM API response schema.
The production IAM/policy adapter and AWE expression binding remain gated.
Inputs must be obtained server-side; intake/notification approver IDs are ignored.
"""
from collections.abc import Mapping
from dataclasses import dataclass
from .profile import FarmerReferenceError


FARMER_APPROVER_ROLE = "Farmer Reference Approver"


@dataclass(frozen=True)
class ApproverEligibility:
    user_id: str
    functional_roles: frozenset[str]
    # Canonical Master Data IDs resolved from registry geographic policies.
    # Merely holding a DP_ role does not supply a scope until policy resolution.
    woreda_ids: frozenset[str]
    active: bool = True


def routing_woreda(action: str, *, verified_source: Mapping | None = None,
                   approved_local: Mapping | None = None) -> str:
    if action == "ADD":
        profile = verified_source
    elif action == "UPDATE":
        profile = approved_local
    else:
        raise FarmerReferenceError("FARMER_REFERENCE_UNSUPPORTED_ACTION")
    value = profile.get("woreda_id") if isinstance(profile, Mapping) else None
    if not isinstance(value, str) or not value.strip():
        raise FarmerReferenceError("FARMER_REFERENCE_APPROVED_SCOPE_REQUIRED")
    # Never fall back from a missing canonical ID to a human name or a proposed
    # UPDATE address. Exact identifiers are supplied by the Master Data adapter.
    return value.strip()


def approver_context(action: str, candidates: tuple[ApproverEligibility, ...], *,
                     verified_source: Mapping | None = None,
                     approved_local: Mapping | None = None) -> dict:
    woreda_id = routing_woreda(action, verified_source=verified_source, approved_local=approved_local)
    user_ids = sorted({candidate.user_id for candidate in candidates
                       if candidate.active and isinstance(candidate.user_id, str) and candidate.user_id.strip()
                       and candidate.user_id == candidate.user_id.strip()
                       and FARMER_APPROVER_ROLE in candidate.functional_roles
                       and woreda_id in candidate.woreda_ids})
    if not user_ids:
        raise FarmerReferenceError("FARMER_REFERENCE_NO_ELIGIBLE_APPROVER")
    return {"farmer_reference_woreda_id": woreda_id, "farmer_reference_approver_ids": user_ids}
