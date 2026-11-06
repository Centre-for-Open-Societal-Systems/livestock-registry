"""Facts about a Farmer-reference change that an approval policy may test.

The registry sends these two keys with every Farmer-reference approval request.
They are plain context, not a decision: whether a human reviews the change is
decided by the approval policy bound to the Farmer section (a `skip_if` rule on
its stages), never by this code.
"""
FARMER_REGISTRY_SOURCE = "farmer-registry"
UNVERIFIED_SOURCE = "unverified"
# Declared on the policy binding (context_field_names) so the platform copies
# exactly these keys into the approval request context.
CONTEXT_FIELD_NAMES = ["change_type", "source"]


def approval_context(action, *, response_digest, source_system, configured_source_system=""):
    """Return {"change_type", "source"} for one ledger request.

    configured_source_system is the Farmer source system this deployment is configured for
    (the caller reads it with farmer_reference.configuration.setting("SOURCE_ID")).
    change_type is the request action, ADD or UPDATE. source is
    "farmer-registry" only when the ledger holds the digest of a signed lookup
    response and the reference was bound to the configured Farmer source
    system; anything else is "unverified", so a missing configuration can only
    ever keep a human in the loop.
    """
    configured = (configured_source_system or "").strip()
    verified = bool(response_digest) and bool(configured) and source_system == configured
    return {"change_type": action, "source": FARMER_REGISTRY_SOURCE if verified else UNVERIFIED_SOURCE}
