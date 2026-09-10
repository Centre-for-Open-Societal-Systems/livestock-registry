import logging
import re
import uuid
from datetime import date, datetime, timezone

from openg2p_registry_core.models import (
    G2PFunctionalIdGenerationQueue,
    G2PRegisterChangeRequest,
)
from openg2p_registry_core.services import G2PRegisterDomainService
from sqlalchemy import select

from .audit_snapshot import AuditSnapshotMixin

from .domain_validation_utils import (
    _animal_models,
    as_int,
    ear_tag_exists,
    is_blank,
    parse_date,
    validate_species_matches,
    validation_error,
)

_logger = logging.getLogger("g2p-register-domain-service")

# Vital Event's own register_id and its sibling Animal's, from
# g2p_register_definitions.sql (both share master_register_id = the Livestock
# register). Used by post_approve, below, to auto-create offspring on a Birth
# event — mirrors LAND_REGISTER_ID/HOUSEHOLD_REGISTER_ID in the Farmer
# extension's own domain service.
VITAL_EVENT_REGISTER_ID = "76811bf6-07df-5ed4-9466-13b782f627fe"
ANIMAL_REGISTER_ID = "041a9f79-2142-548a-a15b-a4c76fc9f6f7"

# ET followed by exactly 10 digits — same format G2PRegisterDomainServiceAnimal
# enforces on a manually-entered ear tag (_EAR_TAG_PATTERN there).
_EAR_TAG_PATTERN = re.compile(r"^ET(\d{10})$")

# field -> human label used in the "Please provide the ... " message, mirroring
# the fields marked "widget-required" on the Vital Event Details form.
_REQUIRED_FIELDS = {
    "ear_tag_id": "livestock ear tag",
    "species": "species",
    "event_type": "event type",
    "event_date": "event date",
}


class G2PRegisterDomainServiceVitalEvent(AuditSnapshotMixin, G2PRegisterDomainService):

    async def validate_domain_attributes(self, records: list[dict]):
        for record in records:
            self._validate_required_fields(record)
            self._validate_disease_type(record)
            await self._validate_ear_tag_exists(record)
            await validate_species_matches(record)
            self._validate_not_in_future(record, "event_date")
            self._validate_not_in_future(record, "date_onset")
            self._validate_date_order(record, "date_onset", "date_resolution")
            self._validate_offspring_count(record)

    def _validate_required_fields(self, record: dict) -> None:
        for field, label in _REQUIRED_FIELDS.items():
            if is_blank(record.get(field)):
                validation_error(f"Please provide the {label} before saving the record.")

    def _validate_disease_type(self, record: dict) -> None:
        # Only a DISEASE vital event carries a diagnosis — the form hides
        # disease_type for BIRTH/MORTALITY, so it must not be required there.
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

    def _validate_offspring_count(self, record: dict) -> None:
        is_birth = str(record.get("event_type") or "").upper() == "BIRTH"

        # Only births carry offspring; a non-birth event with a count is a
        # data-entry slip worth rejecting rather than silently storing.
        count = as_int(record.get("offspring_count"))
        if count is not None:
            if count < 0:
                validation_error("offspring_count must not be negative")
            if count > 0 and not is_birth:
                validation_error("offspring_count is only valid on a BIRTH event")

        if not is_birth:
            return

        # A Birth event without a count/sex can't generate the offspring
        # Animal profile(s) post_approve is about to create below — required
        # here, not left to silently produce zero animals.
        if count is None or count < 1:
            validation_error("Please provide the number of offspring before saving the record.")
        if is_blank(record.get("offspring_gender")):
            validation_error("Please provide the sex of the offspring before saving the record.")

    async def post_approve(self, change_request: G2PRegisterChangeRequest, session) -> None:
        """BIRTH event -> auto-create the newborn Animal profile(s) under
        Livestock Details, with a freshly generated ear tag each — mirrors
        g2p.livestock.vital.event._create_offspring_profiles in the Odoo
        module (g2p_livestock_registry/models/livestock_event.py).

        Covers the CHANGE REQUEST path: a Birth event added/edited against a
        Livestock record that is already an approved register entry. See
        post_ingest, below, for the other way a Birth event reaches this
        table — a still-draft record's *first* approval.
        """
        if change_request.section_register_id != VITAL_EVENT_REGISTER_ID:
            return

        # Resolved through the "openg2p_registry_extensions" alias, not a
        # relative "..models" import — this method is reached via
        # G2PRegisterDomainFactory.get_domain_service, which imports THIS
        # service module by its real dotted name
        # ("openg2p_registry_livestock_extension...", see factory/
        # g2p_register_domain_factory.py); a relative import from here would
        # re-import models.py under that real name too, and SQLAlchemy
        # refuses the second declarative Table registration. Same reasoning
        # as domain_validation_utils._animal_models, just for VitalEvent.
        import importlib

        G2PRegisterVitalEvent = importlib.import_module(
            "openg2p_registry_extensions.register_domain.models"
        ).G2PRegisterVitalEvent

        vital_event = (
            await session.execute(
                select(G2PRegisterVitalEvent).where(
                    G2PRegisterVitalEvent.internal_record_id == change_request.internal_record_id
                )
            )
        ).scalar_one_or_none()
        if not vital_event:
            return
        await self._maybe_generate_offspring(vital_event, session)

    async def post_ingest(self, register_id: str, register_row, session) -> None:
        """Same offspring auto-creation as post_approve, above, but for a
        Birth event that reaches the register by a still-draft submission's
        FIRST approval (intake_form_register_ingest_worker converting the
        whole submission's rows from intake-form drafts into real register
        rows — see G2PRegisterDomainServiceFarmer.post_ingest for the same
        two-hooks-one-effect pattern). register_row here IS the just-inserted
        G2PRegisterVitalEvent — no lookup needed, unlike post_approve.
        """
        if register_id != VITAL_EVENT_REGISTER_ID:
            return
        await self._maybe_generate_offspring(register_row, session)

    async def _maybe_generate_offspring(self, vital_event, session) -> None:
        if str(vital_event.event_type or "").upper() != "BIRTH":
            return
        if vital_event.offspring_generated:
            return  # already generated for this event — never double-create

        count = as_int(vital_event.offspring_count) or 0
        if count < 1:
            return

        await self._create_offspring_animals(vital_event, count, session)
        vital_event.offspring_generated = True

    async def _create_offspring_animals(self, vital_event, count: int, session) -> None:
        from .g2p_register_domain_service_animal import G2PRegisterDomainServiceAnimal

        G2PRegisterAnimal, G2PIntakeFormAnimal = _animal_models()

        # Breed isn't captured on the Vital Event itself (species is, via the
        # ear_tag_id autofill from Livestock Details) — copied from the dam's
        # own Animal row instead, same as the Odoo module's
        # _create_offspring_profiles. Best-effort: a dam with no breed on
        # file, or not found at all, just leaves the offspring's breed blank
        # for staff to fill in — this never blocks offspring creation.
        dam = (
            await session.execute(
                select(G2PRegisterAnimal).where(
                    G2PRegisterAnimal.ear_tag_id == vital_event.ear_tag_id,
                    G2PRegisterAnimal.link_internal_record_id == vital_event.link_internal_record_id,
                )
            )
        ).scalar()
        breed = dam.breed if dam else None

        next_tag_number = await self._next_ear_tag_number(session, G2PRegisterAnimal, G2PIntakeFormAnimal)

        animal_service = G2PRegisterDomainServiceAnimal()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        actor = vital_event.last_approved_by or vital_event.created_by

        created_tags = []
        for _ in range(count):
            # ear_tag_id is always exactly ET + 10 digits (_EAR_TAG_PATTERN,
            # enforced on manual entry by G2PRegisterDomainServiceAnimal); a
            # sequence at the ceiling would silently overflow into 11 digits
            # here since :010d only pads, never truncates — reject instead of
            # inserting an offspring whose ear tag no longer matches the
            # format anything else validates against.
            if next_tag_number > 9999999999:
                validation_error(
                    "Cannot generate a new ear tag: the ET0000000000-ET9999999999 "
                    "sequence is exhausted."
                )
            ear_tag_id = f"ET{next_tag_number:010d}"
            next_tag_number += 1
            internal_id = str(uuid.uuid4())

            payload = {
                "ear_tag_id": ear_tag_id,
                "species": vital_event.species,
                "breed": breed,
                "gender": vital_event.offspring_gender,
                "date_of_birth": vital_event.event_date,
                "registration_date": vital_event.event_date,
                "health_status": "HEALTHY",
                "vaccination_status": "NONE",
                # DRAFT, not CONFIRMED/DONE: a newborn profile is legitimately
                # incomplete (no breed found, weight not yet taken, ...) —
                # same as the Odoo module's 'state': 'draft' — pending staff
                # completing it under Livestock Details.
                "state": "DRAFT",
            }

            animal = G2PRegisterAnimal(
                internal_record_id=internal_id,
                link_internal_record_id=vital_event.link_internal_record_id,
                record_status="ACTIVE",
                created_by=actor,
                created_at=now,
                last_approved_by=actor,
                last_approved_at=now,
                **payload,
            )
            animal.record_name = animal_service.construct_record_name(payload)
            animal.search_text = animal_service.construct_search_text(payload)
            session.add(animal)

            # Insert the row directly, then enqueue functional-id generation —
            # the existing celery worker assigns the real AN-########## id
            # exactly as it would for any other new Animal record (mirrors
            # G2PRegisterDomainServiceFarmer._create_household_for_head).
            session.add(
                G2PFunctionalIdGenerationQueue(
                    register_id=ANIMAL_REGISTER_ID,
                    internal_record_id=internal_id,
                )
            )
            created_tags.append(ear_tag_id)

        await session.flush()
        _logger.info(
            "Birth event %s: created %d offspring Animal row(s) under livestock %s: %s",
            vital_event.internal_record_id, count, vital_event.link_internal_record_id, created_tags,
        )

    async def _next_ear_tag_number(self, session, G2PRegisterAnimal, G2PIntakeFormAnimal) -> int:
        """The next unused ET+10-digit sequence number, one higher than the
        highest already in use anywhere — the approved register, or a
        still-pending intake draft. Mirrors _generate_next_ear_tag in the
        Odoo module, but computes the whole batch's starting point once
        rather than re-querying per offspring.
        """
        max_num = 0
        for model in (G2PRegisterAnimal, G2PIntakeFormAnimal):
            tags = (
                await session.execute(select(model.ear_tag_id).where(model.ear_tag_id.like("ET%")))
            ).scalars().all()
            for tag in tags:
                match = _EAR_TAG_PATTERN.match((tag or "").strip().upper())
                if match:
                    max_num = max(max_num, int(match.group(1)))
        return max_num + 1

    def construct_search_text(self, payload: dict, extra: list[str] = None) -> str:
        _logger.info("Constructing search text for vital event record")

        keys = [
            "functional_record_id",
            "ear_tag_id",
            "species",
            "event_type",
            "cause",
            "disease_type",
            "veterinarian_name",
            "reporting_officer",
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
        _logger.info("Constructing record name for vital event record")

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
