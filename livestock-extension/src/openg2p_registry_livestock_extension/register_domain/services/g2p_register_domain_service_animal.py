import logging
import re
from datetime import date

from openg2p_registry_core.services import G2PRegisterDomainService

from .audit_snapshot import AuditSnapshotMixin

from .domain_validation_utils import (
    as_float,
    ear_tag_used_by_other_animal,
    is_blank,
    parse_date,
    validation_error,
)

_logger = logging.getLogger("g2p-register-domain-service")


# ET followed by exactly 10 digits, as enforced by _check_ear_tag_format in
# g2p_livestock_registry/models/live_stock_registry_line.py.
_EAR_TAG_PATTERN = re.compile(r"^ET\d{10}$")

# field -> human label used in the "Please provide the ... " message, mirroring
# the fields marked "widget-required" on the Livestock Details form.
_REQUIRED_FIELDS = {
    "ear_tag_id": "livestock ear tag",
    "species": "species",
    "breed": "breed",
    "gender": "gender",  # G2R-135 mandatory constraint
    "date_of_birth": "date of birth",
    "vaccination_status": "vaccination status",
    "health_status": "health status",
    "registration_date": "registration date",
}


class G2PRegisterDomainServiceAnimal(AuditSnapshotMixin, G2PRegisterDomainService):

    async def validate_domain_attributes(self, records: list[dict]):
        for record in records:
            self._validate_required_fields(record)
            self._validate_ear_tag_id(record)
            self._validate_not_in_future(record, "date_of_birth")
            self._validate_not_in_future(record, "registration_date")
            self._validate_weight(record)
            self._populate_age_from_date_of_birth(record)
        # Runs only once every record above has passed — so by this point
        # every ear_tag_id/species/breed used below is known non-blank and
        # already in the normalized ET+10-digit form.
        await self._validate_no_duplicate_ear_tags(records)

    def _validate_required_fields(self, record: dict) -> None:
        for field, label in _REQUIRED_FIELDS.items():
            if is_blank(record.get(field)):
                validation_error(f"Please provide the {label} before saving the record.")

    def _validate_ear_tag_id(self, record: dict) -> None:
        value = record.get("ear_tag_id")
        if value is None or str(value).strip() == "":
            return
        normalized = re.sub(r"\s+", "", str(value)).upper()
        if not _EAR_TAG_PATTERN.match(normalized):
            validation_error(
                "ear_tag_id must be ET followed by exactly 10 digits, e.g. ET0000000013"
            )
        # Store the normalized form, not whatever casing/spacing was typed —
        # otherwise "et5678765435" and "ET5678765435" would both pass this
        # check yet be treated as different tags by the duplicate check
        # below (and by ear_tag_exists/get_animal_species elsewhere).
        record["ear_tag_id"] = normalized

    async def _validate_no_duplicate_ear_tags(self, records: list[dict]) -> None:
        """Two different animals must never share an ear tag with the same
        species and breed — mirroring the Old System's duplicate check,
        which this section had no equivalent of at all. Two layers:

        1. Within this same save (this farmer's own rows, all sent together
           every time one row is saved): caught by the `seen` dict below,
           no DB round trip needed.
        2. Against everything else already saved anywhere — a different
           farmer's animal, or one already approved into the register: the
           `ear_tag_used_by_other_animal` DB check, which excludes this
           submission's own rows so re-saving an animal you already
           registered isn't flagged as a duplicate of itself.
        """
        self_ids = {
            str(record["internal_record_id"])
            for record in records
            if record.get("internal_record_id")
        }

        seen: dict[tuple, str] = {}
        for record in records:
            ear_tag_id = record.get("ear_tag_id")
            if is_blank(ear_tag_id):
                continue
            key = (ear_tag_id, record.get("species"), record.get("breed"))
            if key in seen:
                validation_error(
                    f"ear_tag_id '{ear_tag_id}' is used by more than one animal of the "
                    "same species and breed in this record."
                )
            seen[key] = ear_tag_id

            if await ear_tag_used_by_other_animal(
                ear_tag_id,
                record.get("species"),
                record.get("breed"),
                exclude_internal_record_ids=self_ids,
            ):
                validation_error(
                    f"ear_tag_id '{ear_tag_id}' is already registered to a different "
                    "animal of the same species and breed."
                )

    def _validate_not_in_future(self, record: dict, field: str) -> None:
        value = parse_date(record.get(field))
        if value is not None and value > date.today():
            validation_error(f"{field} must not be in the future")

    def _validate_weight(self, record: dict) -> None:
        weight = as_float(record.get("weight"))
        if weight is not None and weight <= 0:
            validation_error("weight must be greater than zero")

    def _populate_age_from_date_of_birth(self, record: dict) -> None:
        """Derive the stored Age display string from date_of_birth, the same
        way `g2p.livestock.registry.line._compute_age` did in the Odoo module.
        Overwrites whatever was submitted for "age" — it is a display value
        derived from date_of_birth, not independent input.
        """
        birth_date = parse_date(record.get("date_of_birth"))
        if birth_date is None:
            record["age"] = None
            return
        years, months = self._calculate_age_years_months(birth_date)
        record["age"] = f"{years} years, {months} months"

    @staticmethod
    def _calculate_age_years_months(birth_date: date) -> tuple[int, int]:
        today = date.today()
        years = today.year - birth_date.year
        months = today.month - birth_date.month
        if today.day < birth_date.day:
            months -= 1
        if months < 0:
            years -= 1
            months += 12
        return years, months

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
