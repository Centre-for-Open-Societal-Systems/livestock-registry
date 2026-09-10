import logging
import re
from datetime import date

from openg2p_registry_core.models import G2PRegisterChangeRequest
from openg2p_registry_core.services import G2PRegisterDomainService
from sqlalchemy import select

from .audit_snapshot import AuditSnapshotMixin

from .domain_validation_utils import parse_date, validation_error

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

# Livestock's own register_id and Farmer's, from g2p_register_definitions.sql.
# Farmer and Livestock are SIBLING top-level registers (both master_register_id
# NULL) submitted together on one form, not parent/child — so there is no
# link_internal_record_id set by the platform itself the way a true child
# section gets one. post_approve/post_ingest below establish it.
LIVESTOCK_REGISTER_ID = "997676d3-7008-59f9-b23e-613ad79bbb08"
FARMER_REGISTER_ID = "f9c6a359-9563-5a43-b0fe-6c7e452037a3"


def _extension_models():
    """Import the extension's own models the same way the platform resolves
    the domain extension: through the "openg2p_registry_extensions" alias
    main.py points at this package's real module in sys.modules, not this
    package's own dotted name — see domain_validation_utils._animal_models's
    docstring for the full reasoning. Matters here specifically because
    G2PRegisterDomainFactory.get_domain_service (factory/g2p_register_domain_
    factory.py) resolves THIS service by importing
    "openg2p_registry_livestock_extension.register_domain.services" — the
    real name — so a plain "from ..models import ..." inside a method reached
    that way re-imports models.py under the real name too, and SQLAlchemy
    refuses the second declarative Table registration.
    """
    import importlib

    return importlib.import_module("openg2p_registry_extensions.register_domain.models")


class G2PRegisterDomainServiceLivestock(AuditSnapshotMixin, G2PRegisterDomainService):

    async def validate_domain_attributes(self, records: list[dict]):
        for record in records:
            # NOT required here, unlike the Farmer register's own copy of
            # these two fields: the "Farmer Details" section's farmer_id/
            # fayda_fan_id are a display-only mirror of the linked Farmer and
            # are never actually populated through this per-section save (see
            # g2p_intake_form_livestocks — 0/23 rows have ever had a
            # non-blank farmer_id here); they get copied over from the Farmer
            # register at finalize/approval time instead. Requiring them here
            # blocked every Livestock intake at this section regardless of
            # what the user typed.
            self._validate_farmer_id(record)
            self._validate_fayda_fan_id(record)
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

    async def post_approve(self, change_request: G2PRegisterChangeRequest, session) -> None:
        """Copy the linked Farmer's identity onto this Livestock record —
        see validate_domain_attributes' comment above: farmer_id/fayda_fan_id/
        farmer_name here are meant to be "a display-only mirror ... copied
        over from the Farmer register at finalize/approval time", but nothing
        had ever actually performed that copy (hence "0/23 rows have ever had
        a non-blank farmer_id here"). Covers editing an already-approved
        Livestock record; see post_ingest, below, for a still-draft record's
        first approval.
        """
        if change_request.section_register_id != LIVESTOCK_REGISTER_ID:
            return

        G2PRegisterLivestock = _extension_models().G2PRegisterLivestock

        livestock = (
            await session.execute(
                select(G2PRegisterLivestock).where(
                    G2PRegisterLivestock.internal_record_id == change_request.internal_record_id
                )
            )
        ).scalar_one_or_none()
        if not livestock:
            return
        await self._sync_farmer_identity(livestock, session)

    async def post_ingest(self, register_id: str, register_row, session) -> None:
        """Same Farmer-identity sync as post_approve, above, for a Livestock
        record reaching the register via a still-draft submission's first
        approval. Safe to run here: the form's own section order (section_order
        10 for Farmer Details vs. 30+ for every Livestock section) guarantees
        the sibling Farmer row this submission carries is already inserted —
        and its history row already recorded — by the time this fires.
        """
        if register_id != LIVESTOCK_REGISTER_ID:
            return
        await self._sync_farmer_identity(register_row, session)

    async def _sync_farmer_identity(self, livestock, session) -> None:
        G2PRegisterFarmer = _extension_models().G2PRegisterFarmer

        farmer_internal_id = livestock.farmer_uuid or await self._find_sibling_farmer_internal_record_id(
            livestock, session
        )
        if not farmer_internal_id:
            return

        farmer = (
            await session.execute(
                select(G2PRegisterFarmer).where(
                    G2PRegisterFarmer.internal_record_id == farmer_internal_id
                )
            )
        ).scalar_one_or_none()
        if not farmer:
            return

        livestock.farmer_uuid = farmer_internal_id
        livestock.farmer_id = farmer.farmer_id
        livestock.fayda_fan_id = farmer.fayda_fan_id
        livestock.farmer_name = farmer.farmer_name
        # Mirrors the Fayda FAN into link_foundational_id — see G2PLivestock's
        # own module docstring and G2PFarmer's identical comment on this field.
        livestock.link_foundational_id = farmer.fayda_fan_id

    async def _find_sibling_farmer_internal_record_id(self, livestock, session) -> str | None:
        """This Livestock record's own submission_id, off its most recent
        history row, joined back to whichever Farmer register history row
        shares that same submission_id — i.e. the Farmer submitted alongside
        it on the same form. Farmer and Livestock have no other relationship
        the platform tracks (see LIVESTOCK_REGISTER_ID's comment above), so
        this is the only thing connecting them.
        """
        models = _extension_models()
        G2PRegisterHistoryFarmer = models.G2PRegisterHistoryFarmer
        G2PRegisterHistoryLivestock = models.G2PRegisterHistoryLivestock

        submission_id = (
            await session.execute(
                select(G2PRegisterHistoryLivestock.submission_id)
                .where(G2PRegisterHistoryLivestock.internal_record_id == livestock.internal_record_id)
                .where(G2PRegisterHistoryLivestock.submission_id.is_not(None))
                .order_by(G2PRegisterHistoryLivestock.created_at.asc())
                .limit(1)
            )
        ).scalar()
        if not submission_id:
            return None

        return (
            await session.execute(
                select(G2PRegisterHistoryFarmer.internal_record_id)
                .where(G2PRegisterHistoryFarmer.submission_id == submission_id)
                .order_by(G2PRegisterHistoryFarmer.created_at.asc())
                .limit(1)
            )
        ).scalar()

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
        _logger.info("Constructing record name for livestock record")

        # Farmer name only. Appending the OAN id here put the name and a long
        # identifier on one line in the register list, where the id is already
        # shown as its own column.
        keys = ["farmer_name"]
        record_name = []
        if extra:
            record_name.extend(str(item).strip() for item in extra if str(item).strip())
        record_name.extend(
            str(payload.get(key) or "").strip()
            for key in keys
            if str(payload.get(key) or "").strip()
        )

        return " ".join(record_name).strip()
