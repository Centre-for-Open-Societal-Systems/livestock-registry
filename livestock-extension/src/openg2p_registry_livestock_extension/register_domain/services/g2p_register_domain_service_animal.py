import logging
from datetime import date

from openg2p_registry_core.services import G2PRegisterDomainService

from .domain_validation_utils import as_float, parse_date, validation_error

_logger = logging.getLogger("g2p-register-domain-service")


class G2PRegisterDomainServiceAnimal(G2PRegisterDomainService):

    async def validate_domain_attributes(self, records: list[dict]):
        for record in records:
            self._validate_not_in_future(record, "date_of_birth")
            self._validate_not_in_future(record, "registration_date")
            self._validate_weight(record)

    def _validate_not_in_future(self, record: dict, field: str) -> None:
        value = parse_date(record.get(field))
        if value is not None and value > date.today():
            validation_error(f"{field} must not be in the future")

    def _validate_weight(self, record: dict) -> None:
        weight = as_float(record.get("weight"))
        if weight is not None and weight <= 0:
            validation_error("weight must be greater than zero")

    def construct_search_text(self, payload: dict, extra: list[str] = None) -> str:
        _logger.info("Constructing search text for animal record")

        keys = [
            "functional_record_id",
            "ear_tag_id",
            "secondary_identifier",
            "animal_name",
            "species",
            "breed",
            "gender",
            "health_status",
            "vaccination_status",
            "state",
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
        _logger.info("Constructing record name for animal record")

        keys = ["ear_tag_id", "species"]
        record_name = []
        if extra:
            record_name.extend(str(item).strip() for item in extra if str(item).strip())
        record_name.extend(
            str(payload.get(key) or "").strip()
            for key in keys
            if str(payload.get(key) or "").strip()
        )

        return " ".join(record_name).strip()
