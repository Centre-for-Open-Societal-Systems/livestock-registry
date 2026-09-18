import logging
import re
from datetime import date

from openg2p_registry_core.services import G2PRegisterDomainService

from .audit_snapshot import AuditSnapshotMixin

from .domain_validation_utils import (
    compose_farmer_name,
    is_blank,
    parse_date,
    require_field,
    sync_farmer_identity_to_livestock,
    validation_error,
)

_logger = logging.getLogger("g2p-register-domain-service")


# FR- followed by exactly 10 digits, as enforced by _check_farmer_id_format in
# g2p_livestock_registry/models/livestock_registry.py.
_FARMER_ID_PATTERN = re.compile(r"^FR-\d{10}$")
# FAN- followed by exactly 16 digits, as enforced by _check_fayda_fan_id_format in
# g2p_livestock_registry/models/livestock_registry.py.
_FAYDA_FAN_ID_PATTERN = re.compile(r"^FAN-\d{16}$")
# Ethiopian mobile numbers only, matching _check_mobile_numbers in gen1's
# g2p_crop_registry/model/crop_registry.py: +251 or a leading 0, followed by
# 7 or 9 (the only leading digits Ethiopian mobile numbers use) and 8 more
# digits, e.g. +251911223344 or 0911223344.
_MOBILE_NUMBER_PATTERN = re.compile(r"^(\+251[79]\d{8}|0[79]\d{8})$")


class G2PRegisterDomainServiceFarmer(AuditSnapshotMixin, G2PRegisterDomainService):

    async def validate_domain_attributes(self, records: list[dict]):
        for record in records:
            # Guarded by "key present", not unconditional: the Farmer register
            # also backs the (currently unused-by-intake) Farmer Location
            # section, whose payload never carries farmer_id/fayda_fan_id at
            # all. Requiring them outright would reject that section's save
            # outright since the keys are simply absent, not blank.
            if "farmer_id" in record:
                require_field(record, "farmer_id", "Farmer ID")
            if "fayda_fan_id" in record:
                require_field(record, "fayda_fan_id", "Fayda FAN ID")
            self._fill_farmer_name(record)
            self._validate_farmer_id(record)
            self._validate_fayda_fan_id(record)
            self._validate_mobile_number(record, "mobile_number")
            self._validate_not_in_future(record, "date_of_birth")
            self._validate_not_in_future(record, "registration_date")

    def _fill_farmer_name(self, record: dict) -> None:
        """Compose farmer_name from First / Middle / Last Name when the payload
        carries name parts but no farmer_name of its own. The intake form has
        no farmer_name field, so without this the Farmer register row keeps
        farmer_name NULL, record_name falls back to the bare FR- id, and the
        Livestock record's approval-time mirror copies that NULL over the name
        it had at intake (see G2PRegisterDomainServiceLivestock
        ._sync_farmer_identity). When the payload carries name parts they are
        the source of truth (a name corrected on a reopened draft must not
        keep the old composed value); a payload with no name parts at all
        (API / migration sending farmer_name only) is left alone."""
        if not any(key in record for key in ("first_name", "middle_name", "last_name")):
            return
        composed = compose_farmer_name(
            record.get("first_name"), record.get("middle_name"), record.get("last_name")
        )
        if composed:
            record["farmer_name"] = composed
        elif is_blank(record.get("farmer_name")):
            record["farmer_name"] = None

    def _validate_farmer_id(self, record: dict) -> None:
        value = record.get("farmer_id")
        if value is None or str(value).strip() == "":
            return
        if not _FARMER_ID_PATTERN.match(str(value).strip().upper()):
            validation_error(
                "farmer_id must be FR- followed by exactly 10 digits, e.g. FR-1234567890"
            )

    def _validate_fayda_fan_id(self, record: dict) -> None:
        value = record.get("fayda_fan_id")
        if value is None or str(value).strip() == "":
            return
        if not _FAYDA_FAN_ID_PATTERN.match(str(value).strip().upper()):
            validation_error(
                "fayda_fan_id must be FAN- followed by exactly 16 digits, e.g. FAN-1234567890123456"
            )

    def _validate_mobile_number(self, record: dict, field: str) -> None:
        value = record.get(field)
        if value is None or str(value).strip() == "":
            return
        if not _MOBILE_NUMBER_PATTERN.match(str(value).strip()):
            validation_error(
                f"{field} must be a valid Ethiopian mobile number, "
                "e.g. +251911223344 or 0911223344"
            )

    def _validate_not_in_future(self, record: dict, field: str) -> None:
        value = parse_date(record.get(field))
        if value is not None and value > date.today():
            validation_error(f"{field} must not be in the future")

    def construct_search_text(self, payload: dict, extra: list[str] = None) -> str:
        _logger.info("Constructing search text for farmer record")

        keys = [
            "functional_record_id",
            "farmer_id",
            "fayda_fan_id",
            "farmer_name",
            "first_name",
            "middle_name",
            "last_name",
            "mobile_number",
            "status",
            "region",
            "zone",
            "woreda",
            "kebele",
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
        _logger.info("Constructing record name for farmer record")

        keys = ["farmer_name", "farmer_id"]
        record_name = []
        if extra:
            record_name.extend(str(item).strip() for item in extra if str(item).strip())
        record_name.extend(
            str(payload.get(key) or "").strip()
            for key in keys
            if str(payload.get(key) or "").strip()
        )

        return " ".join(record_name).strip()

    async def post_intake_upsert(self, rows: list, session) -> None:
        """Right after the Farmer section is saved: copy the farmer's identity
        onto this submission's Livestock intake row(s) so the deduplication
        engine (which scores the Livestock register only) has farmer_id /
        fayda_fan_id / farmer_name at intake — see
        sync_farmer_identity_to_livestock."""
        for row in rows:
            await sync_farmer_identity_to_livestock(
                session, getattr(row, "application_reference", None), farmer=row
            )
