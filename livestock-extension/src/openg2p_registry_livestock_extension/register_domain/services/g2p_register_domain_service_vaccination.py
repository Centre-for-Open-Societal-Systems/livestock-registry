import logging
from datetime import date, timedelta

from openg2p_registry_core.models import G2PRegisterChangeRequest
from openg2p_registry_core.services import G2PRegisterDomainService
from sqlalchemy import select

from .audit_snapshot import AuditSnapshotMixin

from .domain_validation_utils import (
    _animal_models, ear_tag_exists, is_blank, parse_date, validate_species_matches, validation_error,
)

_logger = logging.getLogger("g2p-register-domain-service")

# Vaccination's own register_id, from g2p_register_definitions.sql. Used by
# post_approve/post_ingest, below, to auto-sync the linked animal's
# Vaccination Status — mirrors HEALTH_EVENT_REGISTER_ID in
# g2p_register_domain_service_health_event.py.
VACCINATION_REGISTER_ID = "51c1f6d6-856a-5e2f-84e9-ff5abdc4fb75"

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
            await self._populate_next_due_date(record)
            self._validate_date_order(record, "vaccination_date", "next_due_date")

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

    async def _populate_next_due_date(self, record: dict) -> None:
        """Derive next_due_date from vaccination_date + the matching Vaccine
        Schedule's interval_days — the same computation the Old System's
        Vaccine Schedule interval drove, and the one the now off-limits
        registry-platform widget (`widget-date-offset`) used to do purely as
        a live in-dialog preview. Done here instead so it's authoritative on
        save regardless of what the (unmodified) platform's widgets can or
        can't compute — same convention as
        G2PRegisterDomainServiceAnimal._populate_age_from_date_of_birth:
        overwrites whatever was submitted, since it's a derived value, not
        independent input.

        Looks up the APPROVED Vaccine Schedule register, not intake drafts —
        that's the operational, administrator-tuned schedule the overdue
        sweep (vaccination_status_service.py) and reminder task already
        trust. No schedule configured yet for this vaccine/species pair (or
        one not yet approved) leaves next_due_date untouched rather than
        blocking the save — a vaccination is still valid without one.
        """
        vaccination_date = parse_date(record.get("vaccination_date"))
        vaccine_type = record.get("vaccine_type")
        species = record.get("species")
        if vaccination_date is None or is_blank(vaccine_type) or is_blank(species):
            return

        import importlib

        from openg2p_fastapi_common.context import dbengine
        from sqlalchemy import and_
        from sqlalchemy.ext.asyncio import async_sessionmaker

        G2PRegisterVaccineSchedule = importlib.import_module(
            "openg2p_registry_extensions.register_domain.models"
        ).G2PRegisterVaccineSchedule

        session_maker = async_sessionmaker(dbengine.get(), expire_on_commit=False)
        async with session_maker() as session:
            interval_days = (
                await session.execute(
                    select(G2PRegisterVaccineSchedule.interval_days).where(
                        and_(
                            G2PRegisterVaccineSchedule.vaccine_name == vaccine_type,
                            G2PRegisterVaccineSchedule.species == species,
                            G2PRegisterVaccineSchedule.is_active.is_not(False),
                        )
                    )
                )
            ).scalar()

        if interval_days is None:
            return

        record["next_due_date"] = (vaccination_date + timedelta(days=interval_days)).isoformat()

    def _validate_date_order(self, record: dict, earlier: str, later: str) -> None:
        start = parse_date(record.get(earlier))
        end = parse_date(record.get(later))
        if start and end and end < start:
            validation_error(f"{later} must not be before {earlier}")

    async def post_approve(self, change_request: G2PRegisterChangeRequest, session) -> None:
        """A logged Vaccination -> the linked animal's Vaccination Status
        becomes UP_TO_DATE. Mirrors the Old System's create()-time side
        effect (g2p_livestock_registry/models/livestock_event.py:
        `rec.line_id.vaccination_status = 'up_to_date'`), covering the
        CHANGE REQUEST path: a Vaccination added/edited against a Livestock
        record that is already an approved register entry.
        """
        if change_request.section_register_id != VACCINATION_REGISTER_ID:
            return

        import importlib

        G2PRegisterVaccination = importlib.import_module(
            "openg2p_registry_extensions.register_domain.models"
        ).G2PRegisterVaccination

        vaccination = (
            await session.execute(
                select(G2PRegisterVaccination).where(
                    G2PRegisterVaccination.internal_record_id == change_request.internal_record_id
                )
            )
        ).scalar_one_or_none()

        if not vaccination:
            # change_request.internal_record_id is the PARENT Livestock
            # record's id here, not the Vaccination row's own id, for a
            # "new table row" change request — see the identical case
            # (confirmed empirically) documented on
            # G2PRegisterDomainServiceHealthEvent.post_approve. Fall back to
            # the most recently created Vaccination under that parent.
            vaccination = (
                await session.execute(
                    select(G2PRegisterVaccination)
                    .where(G2PRegisterVaccination.link_internal_record_id == change_request.internal_record_id)
                    .order_by(G2PRegisterVaccination.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()

        if not vaccination:
            return
        await self._sync_animal_vaccination_status(vaccination, session)

    async def post_ingest(self, register_id: str, register_row, session) -> None:
        """Same Vaccination Status sync as post_approve, above, but for a
        Vaccination that reaches the register by a still-draft submission's
        FIRST approval. register_row here IS the just-inserted
        G2PRegisterVaccination — no lookup needed, unlike post_approve.
        """
        if register_id != VACCINATION_REGISTER_ID:
            return
        await self._sync_animal_vaccination_status(register_row, session)

    async def _sync_animal_vaccination_status(self, vaccination, session) -> None:
        G2PRegisterAnimal, _ = _animal_models()
        animal = (
            await session.execute(
                select(G2PRegisterAnimal).where(
                    G2PRegisterAnimal.ear_tag_id == vaccination.ear_tag_id,
                    G2PRegisterAnimal.link_internal_record_id == vaccination.link_internal_record_id,
                )
            )
        ).scalar()
        if not animal:
            return
        animal.vaccination_status = "UP_TO_DATE"
        await session.flush()
        _logger.info(
            "Vaccination %s: set animal %s vaccination_status to UP_TO_DATE",
            vaccination.internal_record_id, animal.ear_tag_id,
        )

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
