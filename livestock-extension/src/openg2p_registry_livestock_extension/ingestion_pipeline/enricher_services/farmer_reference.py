"""Validate notification identity only; native CR service fetches current source."""
from openg2p_registry_core.interfaces import G2PPayloadEnricherInterface
from ...farmer_reference.notification import notification_fields


class FarmerChangedEnricher(G2PPayloadEnricherInterface):
    """Enricher of the Farmer registry's change notice (data model FARMER_CHANGED_V1)."""

    def enrich(self, data, session):
        identity = notification_fields(data)
        # Never expand notification demographics into trusted local values.
        return identity


# The name the FARMER_REFERENCE_CHANGED_V1 semantic pattern still names; retired with that data model.
G2PFarmerReferenceNotificationEnricher = FarmerChangedEnricher
