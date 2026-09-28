import logging

from openg2p_registry_core.services import G2PRegisterDomainService

_logger = logging.getLogger("g2p-register-domain-service")


class G2PRegisterDomainServiceAuditLog(G2PRegisterDomainService):

    def construct_search_text(self, payload: dict, extra: list[str] = None) -> str:
        _logger.info("Constructing search text for audit log record")

        keys = [
            "functional_record_id",
            "res_model",
            "action_type",
            "user_name",
            "user_role",
            "ip_address",
            "session_id",
        ]
        search_text = []
        if extra:
            search_text.extend(str(item).strip() for item in extra if str(item).strip())
        search_text.extend(
            str(payload.get(key) or "").strip()
            for key in keys
            if str(payload.get(key) or "").strip()
        )

        return " ".join(search_text).strip()

    def construct_record_name(self, payload: dict, extra: list[str] = None) -> str:
        _logger.info("Constructing record name for audit log record")

        keys = ["action_type", "res_model"]
        record_name = []
        if extra:
            record_name.extend(str(item).strip() for item in extra if str(item).strip())
        record_name.extend(
            str(payload.get(key) or "").strip()
            for key in keys
            if str(payload.get(key) or "").strip()
        )

        return " ".join(record_name).strip()
