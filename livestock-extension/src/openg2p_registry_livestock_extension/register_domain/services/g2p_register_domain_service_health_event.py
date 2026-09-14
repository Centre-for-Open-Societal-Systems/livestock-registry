import logging
from datetime import date

from openg2p_registry_core.models import G2PRegisterChangeRequest
from openg2p_registry_core.services import G2PRegisterDomainService
from sqlalchemy import select

from .audit_snapshot import AuditSnapshotMixin

from .domain_validation_utils import (
    _animal_models, ear_tag_exists, is_blank, parse_date, validate_species_matches, validation_error,
)

_logger = logging.getLogger("g2p-register-domain-service")

# Health Event's own register_id, from g2p_register_definitions.sql. Used by
# post_approve/post_ingest, below, to auto-sync the linked animal's Health
# Status — mirrors VITAL_EVENT_REGISTER_ID in
# g2p_register_domain_service_vital_event.py.
HEALTH_EVENT_REGISTER_ID = "a40e4a02-1b82-5b31-89df-71624bd96545"

# event_type -> the linked animal's new Health Status. Mirrors the Old
# System's create()-time side effect (g2p_livestock_registry/models/
# livestock_event.py G2PLivestockHealthEvent._sync_health_status: disease/
# injury -> 'sick', recovery -> 'healthy'), which Gen2 had no equivalent of —
# recording one of these events left the animal's own Health Status field on
# Livestock Details completely untouched. TREATMENT is deliberately absent
# (not in gen1 either) — administering treatment doesn't by itself say
# whether the animal is now well; a separate DISEASE/INJURY or RECOVERY
# event still carries that call.
_HEALTH_STATUS_BY_EVENT_TYPE = {
    "DISEASE": "SICK",
    "INJURY": "SICK",
    "RECOVERY": "HEALTHY",
}

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

    async def post_approve(self, change_request: G2PRegisterChangeRequest, session) -> None:
        """DISEASE/INJURY event -> the linked animal's Health Status becomes
        SICK; RECOVERY -> HEALTHY. Covers the CHANGE REQUEST path: a Health
        Event added/edited against a Livestock record that is already an
        approved register entry. See post_ingest, below, for the other way
        a Health Event reaches this table — a still-draft record's *first*
        approval. Mirrors G2PRegisterDomainServiceVitalEvent.post_approve.
        """
        if change_request.section_register_id != HEALTH_EVENT_REGISTER_ID:
            return

        # Resolved through the "openg2p_registry_extensions" alias, not a
        # relative "..models" import — same reasoning as
        # G2PRegisterDomainServiceVitalEvent.post_approve and
        # domain_validation_utils._animal_models.
        import importlib

        G2PRegisterHealthEvent = importlib.import_module(
            "openg2p_registry_extensions.register_domain.models"
        ).G2PRegisterHealthEvent

        health_event = (
            await session.execute(
                select(G2PRegisterHealthEvent).where(
                    G2PRegisterHealthEvent.internal_record_id == change_request.internal_record_id
                )
            )
        ).scalar_one_or_none()

        if not health_event:
            # change_request.internal_record_id is the PARENT Livestock
            # record's id here, not the Health Event row's own id — for a
            # "new table row" change request (adding a Health Event to a
            # Livestock record that's already an approved register entry),
            # the platform records no id for the specific child row that
            # was added (confirmed empirically: g2p_register_verifications
            # carries no row for these change requests either). Fall back
            # to the most recently created Health Event under that parent —
            # the row this approval is almost certainly about. Without this
            # fallback, a Health Event added via "Edit Details" on an
            # existing record silently never syncs Health Status at all.
            health_event = (
                await session.execute(
                    select(G2PRegisterHealthEvent)
                    .where(G2PRegisterHealthEvent.link_internal_record_id == change_request.internal_record_id)
                    .order_by(G2PRegisterHealthEvent.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()

        if not health_event:
            return
        await self._sync_animal_health_status(health_event, session)

    async def post_ingest(self, register_id: str, register_row, session) -> None:
        """Same Health Status sync as post_approve, above, but for a Health
        Event that reaches the register by a still-draft submission's FIRST
        approval (intake_form_register_ingest_worker converting the whole
        submission's rows from intake-form drafts into real register rows).
        register_row here IS the just-inserted G2PRegisterHealthEvent — no
        lookup needed, unlike post_approve.
        """
        if register_id != HEALTH_EVENT_REGISTER_ID:
            return
        await self._sync_animal_health_status(register_row, session)

    async def _sync_animal_health_status(self, health_event, session) -> None:
        event_type = str(health_event.event_type or "").upper()
        new_status = _HEALTH_STATUS_BY_EVENT_TYPE.get(event_type)
        if new_status is None:
            return

        G2PRegisterAnimal, _ = _animal_models()
        animal = (
            await session.execute(
                select(G2PRegisterAnimal).where(
                    G2PRegisterAnimal.ear_tag_id == health_event.ear_tag_id,
                    G2PRegisterAnimal.link_internal_record_id == health_event.link_internal_record_id,
                )
            )
        ).scalar()
        if not animal:
            return
        animal.health_status = new_status
        await session.flush()
        _logger.info(
            "%s health event %s: set animal %s health_status to %s",
            event_type, health_event.internal_record_id, animal.ear_tag_id, new_status,
        )

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
