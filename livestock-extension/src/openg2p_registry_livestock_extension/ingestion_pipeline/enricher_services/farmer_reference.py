"""Preserve notification structure; current-source lookup occurs in native CR service."""
from openg2p_registry_core.interfaces import G2PPayloadEnricherInterface


class G2PFarmerReferenceNotificationEnricher(G2PPayloadEnricherInterface):
    def enrich(self, data, session):
        return data
