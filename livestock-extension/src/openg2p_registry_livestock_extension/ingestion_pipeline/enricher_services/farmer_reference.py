"""Validate notification identity only; native CR service fetches current source."""
from openg2p_registry_core.interfaces import G2PPayloadEnricherInterface
from ...farmer_reference.notification import notification_identity


class G2PFarmerReferenceNotificationEnricher(G2PPayloadEnricherInterface):
    def enrich(self, data, session):
        farmer_id, uid = notification_identity(data)
        # Never expand notification demographics into trusted local values.
        return {"farmer_id": farmer_id, "fayda_fan_id": uid}
