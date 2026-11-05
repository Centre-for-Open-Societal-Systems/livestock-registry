"""Facts about a Farmer-reference change that an approval policy may test.

The registry sends these two keys with every Farmer-reference approval request.
They are plain context, not a decision: whether a human reviews the change is
decided by the approval policy bound to the Farmer section (a `skip_if` rule on
its stages), never by this code.
"""
import os

FARMER_REGISTRY_SOURCE = "farmer-registry"
UNVERIFIED_SOURCE = "unverified"
# Declared on the policy binding (context_field_names) so the platform copies
# exactly these keys into the approval request context.
CONTEXT_FIELD_NAMES = ["change_type", "source"]
SOURCE_ID_VARIABLE = "COSS_FARMER_SOURCE_ID"


def approval_context(action, *, response_digest, source_system, configured_source_system=None):
    """Return {"change_type", "source"} for one ledger request.

    change_type is the request action, ADD or UPDATE. source is
    "farmer-registry" only when the ledger holds the digest of a signed lookup
    response and the reference was bound to the configured Farmer source
    system; anything else is "unverified", so a missing configuration can only
    ever keep a human in the loop.
    """
    if configured_source_system is None:
        configured_source_system = os.environ.get(SOURCE_ID_VARIABLE, "")
    configured = (configured_source_system or "").strip()
    verified = bool(response_digest) and bool(configured) and source_system == configured
    return {"change_type": action, "source": FARMER_REGISTRY_SOURCE if verified else UNVERIFIED_SOURCE}
