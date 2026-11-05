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


def finite_woredas(expression, depth=0):
    """Resolve the supported finite subset of standard policy filter trees."""
    if depth > 10 or not isinstance(expression, dict):
        raise FarmerReferenceError("FARMER_REFERENCE_UNSUPPORTED_GEOGRAPHIC_POLICY")
    if expression.get("type") == "CONDITION" and expression.get("field_id") == "woreda_id":
        operator = expression.get("operator", "").lower()
        values = [expression.get("value")] if operator == "eq" else expression.get("values") if operator == "in" else None
        if not isinstance(values, list) or not values or any(not isinstance(value, str) or not value.strip() for value in values):
            raise FarmerReferenceError("FARMER_REFERENCE_UNSUPPORTED_GEOGRAPHIC_POLICY")
        return set(values)
    if expression.get("type") == "GROUP" and expression.get("operator") in {"AND", "OR"}:
        children = expression.get("children")
        if not isinstance(children, list) or not children or len(children) > 100:
            raise FarmerReferenceError("FARMER_REFERENCE_UNSUPPORTED_GEOGRAPHIC_POLICY")
        sets = [finite_woredas(child, depth + 1) for child in children]
        return set.intersection(*sets) if expression["operator"] == "AND" else set.union(*sets)
    raise FarmerReferenceError("FARMER_REFERENCE_UNSUPPORTED_GEOGRAPHIC_POLICY")


def policy_woredas(policies):
    allow, deny = set(), set()
    for policy in policies:
        scopes = finite_woredas(policy.policy_filter_expression)
        if policy.policy_type == "ALLOW":
            allow.update(scopes)
        elif policy.policy_type == "DISALLOW":
            deny.update(scopes)
        else:
            raise FarmerReferenceError("FARMER_REFERENCE_UNSUPPORTED_GEOGRAPHIC_POLICY")
    return frozenset(allow - deny)
