import logging
from typing import Dict

from openg2p_registry_core.interfaces import G2PPayloadEnricherInterface
from sqlalchemy.orm import Session

_logger = logging.getLogger('g2p-payload-enricher-service')

# DCI Payload Enrichers
class G2PDciLivestockCreateEnricherService(G2PPayloadEnricherInterface):
    def enrich(self, data: Dict, session: Session) -> Dict:
        _logger.info("Processing G2PDciLivestockCreateEnricherService")
        return data

class G2PDciLivestockUpdateEnricherService(G2PPayloadEnricherInterface):
    def enrich(self, data: Dict, session: Session) -> Dict:
        _logger.info("Processing G2PDciLivestockUpdateEnricherService")
        return data

class G2PDciLivestockDeleteEnricherService(G2PPayloadEnricherInterface):
    def enrich(self, data: Dict, session: Session) -> Dict:
        _logger.info("Processing G2PDciLivestockDeleteEnricherService")
        return data

# SPDCI Payload Enrichers
class G2PSpdciLivestockCreateEnricherService(G2PPayloadEnricherInterface):
    def enrich(self, data: Dict, session: Session) -> Dict:
        _logger.info("Processing G2PSpdciLivestockCreateEnricherService")
        return data

class G2PSpdciLivestockUpdateEnricherService(G2PPayloadEnricherInterface):
    def enrich(self, data: Dict, session: Session) -> Dict:
        _logger.info("Processing G2PSpdciLivestockUpdateEnricherService")
        return data

class G2PSpdciLivestockDeleteEnricherService(G2PPayloadEnricherInterface):
    def enrich(self, data: Dict, session: Session) -> Dict:
        _logger.info("Processing G2PSpdciLivestockDeleteEnricherService")
        return data

# UNDP Payload Enrichers
class G2PUndpLivestockCreateEnricherService(G2PPayloadEnricherInterface):
    def enrich(self, data: Dict, session: Session) -> Dict:
        _logger.info("Processing G2PUndpLivestockCreateEnricherService")
        return data

class G2PUndpLivestockUpdateEnricherService(G2PPayloadEnricherInterface):
    def enrich(self, data: Dict, session: Session) -> Dict:
        _logger.info("Processing G2PUndpLivestockUpdateEnricherService")
        return data

class G2PUndpLivestockDeleteEnricherService(G2PPayloadEnricherInterface):
    def enrich(self, data: Dict, session: Session) -> Dict:
        _logger.info("Processing G2PUndpLivestockDeleteEnricherService")
        return data
