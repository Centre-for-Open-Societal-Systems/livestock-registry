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
from .domain_validation_utils import event_already_recorded, first_repeated_key

_logger = logging.getLogger("g2p-register-domain-service")

# field -> human label used in the "Please provide the ... " message, mirroring
# the fields marked "widget-required" on the Health Event Details form.
#
# disease_type is NOT here even though the form shows it as required-looking:
# it is only mandatory for a DISEASE event (see _validate_disease_type below,
# mirroring vital_event's _validate_offspring_count) — an INJURY/TREATMENT/
# RECOVERY event hides the field entirely and must not be blocked on it.
_REQUIRED_FIELDS = {
    "ear_tag_id": "livestock ear tag",
    "species": "species",
    "event_type": "event type",
}


class G2PRegisterDomainServiceHealthEvent(AuditSnapshotMixin, G2PRegisterDomainService):

    async def validate_domain_attributes(self, records: list[dict]):
        for record in records:
            self._validate_required_fields(record)
            self._validate_disease_type(record)
            await self._validate_ear_tag_exists(record)
            await validate_species_matches(record)
            self._validate_not_in_future(record, "date_onset")
            self._validate_date_order(record, "date_onset", "date_resolution")
        await self._validate_no_duplicate_events(records)

    def _validate_required_fields(self, record: dict) -> None:
        for field, label in _REQUIRED_FIELDS.items():
            if is_blank(record.get(field)):
                validation_error(f"Please provide the {label} before saving the record.")

    def _validate_disease_type(self, record: dict) -> None:
        # Only a DISEASE event carries a disease — the form hides disease_type
        # for INJURY/TREATMENT/RECOVERY, so it must not be required there.
        if str(record.get("event_type") or "").upper() != "DISEASE":
            return
        if is_blank(record.get("disease_type")):
            validation_error("Please provide the disease before saving the record.")

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
        _logger.info("Constructing search text for health event record")

        keys = [
            "functional_record_id",
            "ear_tag_id",
            "species",
            "event_type",
            "disease_type",
            "treatment",
            "veterinarian_name",
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
        _logger.info("Constructing record name for health event record")

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

    async def _validate_no_duplicate_events(self, records: list[dict]) -> None:
        """The same health event must not be recorded twice for one animal:
        same ear tag, same event type, same disease and same onset date —
        the Old System's _check_duplicate_health_event. Two layers, like
        _validate_no_duplicate_ear_tags on the Animal section: the rows of
        this save first, then the register plus every intake draft
        (excluding this save's own rows, so editing an already-approved
        event isn't flagged against itself). A row without an onset date is
        left alone here — there is nothing to say it is the same event.
        """

        def key_of(record: dict):
            onset = parse_date(record.get("date_onset"))
            if is_blank(record.get("ear_tag_id")) or is_blank(record.get("event_type")) or onset is None:
                return None
            disease = record.get("disease_type")
            return (
                str(record["ear_tag_id"]).strip(),
                str(record["event_type"]).strip().upper(),
                None if is_blank(disease) else str(disease).strip(),
                onset,
            )

        repeated = first_repeated_key(records, key_of)
        if repeated:
            ear_tag_id, event_type, _disease, onset = repeated
            validation_error(
                f"The {event_type} health event for ear tag '{ear_tag_id}' on {onset} "
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
            ear_tag_id, event_type, disease, onset = key
            if await event_already_recorded(
                "HealthEvent",
                {
                    "ear_tag_id": ear_tag_id,
                    "event_type": event_type,
                    "disease_type": disease,
                    "date_onset": onset,
                },
                exclude_internal_record_ids=self_ids,
            ):
                validation_error(
                    f"A {event_type} health event for ear tag '{ear_tag_id}' on {onset} "
                    "is already recorded."
                )
