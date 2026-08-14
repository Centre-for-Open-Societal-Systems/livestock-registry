import logging
import re
from datetime import date

from openg2p_registry_core.services import G2PRegisterDomainService

from .domain_validation_utils import parse_date, validation_error

_logger = logging.getLogger("g2p-register-domain-service")


# FR- followed by exactly 10 digits, as enforced by _check_farmer_id_format in
# g2p_livestock_registry/models/livestock_registry.py.
_FARMER_ID_PATTERN = re.compile(r"^FR-\d{10}$")
_MOBILE_NUMBER_PATTERN = re.compile(r"^\+?[0-9][0-9\- ]{5,19}$")


class G2PRegisterDomainServiceLivestock(G2PRegisterDomainService):

    async def validate_domain_attributes(self, records: list[dict]):
        for record in records:
            self._validate_farmer_id(record)
            self._validate_mobile_number(record, "surveyor_mobile_number")
            self._validate_mobile_number(record, "supervisor_mobile_number")
            self._validate_not_in_future(record, "registration_date")

    def _validate_farmer_id(self, record: dict) -> None:
        value = record.get("farmer_id")
        if value is None or str(value).strip() == "":
            return
        if not _FARMER_ID_PATTERN.match(str(value).strip().upper()):
            validation_error(
                "farmer_id must be FR- followed by exactly 10 digits, e.g. FR-1234567890"
            )

    def _validate_mobile_number(self, record: dict, field: str) -> None:
        value = record.get(field)
        if value is None or str(value).strip() == "":
            return
        if not _MOBILE_NUMBER_PATTERN.match(str(value).strip()):
            validation_error(f"{field} is not a valid mobile number")

    def _validate_not_in_future(self, record: dict, field: str) -> None:
        value = parse_date(record.get(field))
        if value is not None and value > date.today():
            validation_error(f"{field} must not be in the future")

    def construct_search_text(self, payload: dict, extra: list[str] = None) -> str:
        _logger.info("Constructing search text for livestock record")

        keys = [
            "functional_record_id",
            "oan_id",
            "farmer_name",
            "farmer_id",
            "fayda_fan_id",
            "secondary_identifier",
            "status",
            "state",
            "source_system",
            "surveyor_name",
            "supervisor_name",
            "address_line_1",
            "address_line_2",
            "country_code",
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
        _logger.info("Constructing record name for livestock record")

        keys = ["farmer_name", "oan_id"]
        record_name = []
        if extra:
            record_name.extend(str(item).strip() for item in extra if str(item).strip())
        record_name.extend(
            str(payload.get(key) or "").strip()
            for key in keys
            if str(payload.get(key) or "").strip()
        )

        return " ".join(record_name).strip()
