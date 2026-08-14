import logging
from datetime import date

from openg2p_registry_core.services import G2PRegisterDomainService

from .domain_validation_utils import parse_date, validation_error

_logger = logging.getLogger("g2p-register-domain-service")


class G2PRegisterDomainServiceBreeding(G2PRegisterDomainService):

    async def validate_domain_attributes(self, records: list[dict]):
        for record in records:
            self._validate_not_in_future(record, "breeding_date")
            self._validate_not_in_future(record, "pregnancy_confirmation_date")
            self._validate_date_order(record, "breeding_date", "expected_calving_date")

    def _validate_not_in_future(self, record: dict, field: str) -> None:
        value = parse_date(record.get(field))
        if value is not None and value > date.today():
            validation_error(f"{field} must not be in the future")

    def _validate_date_order(self, record: dict, earlier: str, later: str) -> None:
        start = parse_date(record.get(earlier))
        end = parse_date(record.get(later))
        if start and end and end < start:
            validation_error(f"{later} must not be before {earlier}")

    def construct_search_text(self, payload: dict, extra: list[str] = None) -> str:
        _logger.info("Constructing search text for breeding record")

        keys = [
            "functional_record_id",
            "ear_tag_id",
            "species",
            "event_type",
            "sire_or_semen_id",
            "ai_technician_name",
            "ai_technique",
            "semen_batch_number",
            "outcome",
            "location",
            "location_details",
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
        _logger.info("Constructing record name for breeding record")

        keys = ["event_type", "ear_tag_id"]
        record_name = []
        if extra:
            record_name.extend(str(item).strip() for item in extra if str(item).strip())
        record_name.extend(
            str(payload.get(key) or "").strip()
            for key in keys
            if str(payload.get(key) or "").strip()
        )

        return " ".join(record_name).strip()
