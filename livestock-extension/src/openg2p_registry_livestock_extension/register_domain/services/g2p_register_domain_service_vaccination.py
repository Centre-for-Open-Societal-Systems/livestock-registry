import logging
from datetime import date

from openg2p_registry_core.services import G2PRegisterDomainService

from .audit_snapshot import AuditSnapshotMixin

from .domain_validation_utils import (
    ear_tag_exists, is_blank, parse_date, validate_species_matches, validation_error,
)

# Kept as its own import line rather than folded into the block above: the
# block is edited by other in-flight work on this file, and a separate
# statement keeps the two changes from landing on the same lines.
from .domain_validation_utils import (
    event_already_recorded,
    first_repeated_key,
    humanize_attribute_value,
)

_logger = logging.getLogger("g2p-register-domain-service")

# field -> human label used in the "Please provide the ... " message, mirroring
# the fields marked "widget-required" on the Vaccination Details form.
_REQUIRED_FIELDS = {
    "ear_tag_id": "livestock ear tag",
    "species": "species",
    "vaccine_type": "vaccine",
    "vaccination_date": "vaccination date",
}


class G2PRegisterDomainServiceVaccination(AuditSnapshotMixin, G2PRegisterDomainService):

    async def validate_domain_attributes(self, records: list[dict]):
        for record in records:
            self._validate_required_fields(record)
            await self._validate_ear_tag_exists(record)
            await validate_species_matches(record)
            self._validate_not_in_future(record, "vaccination_date")
            self._validate_date_order(record, "vaccination_date", "next_due_date")
        await self._validate_no_duplicate_events(records)

    def _validate_required_fields(self, record: dict) -> None:
        for field, label in _REQUIRED_FIELDS.items():
            if is_blank(record.get(field)):
                validation_error(f"Please provide the {label} before saving the record.")

    async def _validate_ear_tag_exists(self, record: dict) -> None:
        value = record.get("ear_tag_id")
        if value is None or str(value).strip() == "":
            return
        if not await ear_tag_exists(str(value).strip()):
            validation_error(
                "ear_tag_id does not match any registered or drafted animal. "
                "Add it under Livestock Details first, or check for a typo."
            )

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
        _logger.info("Constructing search text for vaccination record")

        keys = [
            "functional_record_id",
            "ear_tag_id",
            "species",
            "vaccine_type",
            "batch_number",
            "administered_by",
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
        _logger.info("Constructing record name for vaccination record")

        keys = ["vaccine_type", "ear_tag_id"]
        record_name = []
        if extra:
            record_name.extend(str(item).strip() for item in extra if str(item).strip())
        record_name.extend(
            str(payload.get(key) or "").strip()
            for key in keys
            if str(payload.get(key) or "").strip()
        )

        return " ".join(record_name).strip()

    async def _validate_no_duplicate_events(self, records: list[dict]) -> None:
        """The same vaccine must not be recorded twice for one animal on the
        same day: same ear tag, same vaccine, same vaccination date. The Old
        System had no such check for vaccinations (only for health, vital
        and breeding events) — added here because a second identical row
        can only be a data-entry slip, and it would wrongly push the
        animal's next due date. Same two layers as the other event sections:
        this save's own rows, then register + intake drafts excluding this
        save's own rows.
        """

        def key_of(record: dict):
            on = parse_date(record.get("vaccination_date"))
            if is_blank(record.get("ear_tag_id")) or is_blank(record.get("vaccine_type")) or on is None:
                return None
            return (
                str(record["ear_tag_id"]).strip(),
                str(record["vaccine_type"]).strip(),
                on,
            )

        repeated = first_repeated_key(records, key_of)
        if repeated:
            ear_tag_id, vaccine_type, on = repeated
            vaccine_label = await humanize_attribute_value(vaccine_type)
            validation_error(
                f"Vaccine '{vaccine_label}' for ear tag '{ear_tag_id}' on {on} "
                "is entered more than once in this record."
            )

        self_ids = {
            str(record["internal_record_id"])
            for record in records
            if record.get("internal_record_id")
        }
        for record in records:
            key = key_of(record)
            if key is None:
                continue
            ear_tag_id, vaccine_type, on = key
            if await event_already_recorded(
                "Vaccination",
                {"ear_tag_id": ear_tag_id, "vaccine_type": vaccine_type, "vaccination_date": on},
                exclude_internal_record_ids=self_ids,
            ):
                vaccine_label = await humanize_attribute_value(vaccine_type)
                validation_error(
                    f"Vaccine '{vaccine_label}' for ear tag '{ear_tag_id}' on {on} "
                    "is already recorded."
                )
