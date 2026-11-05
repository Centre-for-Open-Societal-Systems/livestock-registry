"""Legacy lookup is intentionally unavailable on the refactor branch.

The signed consent-aware lookup must be wired through the approved-reference
lifecycle before this branch is deployable. No typed demographic fallback.
"""
async def fetch_farmer_record(*args, **kwargs):
    raise ValueError("FARMER_REFERENCE_LIFECYCLE_NOT_AVAILABLE")

def to_farmer_fields(*args, **kwargs):
    raise ValueError("FARMER_REFERENCE_LIFECYCLE_NOT_AVAILABLE")
