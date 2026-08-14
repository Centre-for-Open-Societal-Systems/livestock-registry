"""BREEDING lines — a child of LIVESTOCK.

Mirrors `g2p.livestock.breeding`: natural service and artificial insemination events,
with the AI-specific technician/technique/semen-batch detail alongside the common
pregnancy and outcome tracking.
"""

from openg2p_registry_core.models.g2p_intake_form import G2PIntakeForm
from openg2p_registry_core.models import G2PRegister, G2PRegisterHistory
from sqlalchemy import Boolean, Date, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from ..services import G2PRegisterDomainServiceBreeding
from .enums import BreedingEventTypeEnum, BreedingOutcomeEnum, EventLocationEnum


class G2PBreeding:

    ear_tag_id: Mapped[str] = mapped_column(String, nullable=True)
    species: Mapped[str] = mapped_column(String, nullable=True)  # Attribute lookup (LIVESTOCK_SPECIES)
    event_type: Mapped[BreedingEventTypeEnum] = mapped_column(String, nullable=True)  # BreedingEventTypeEnum
    breeding_date: Mapped[str] = mapped_column(Date, nullable=True)
    sire_or_semen_id: Mapped[str] = mapped_column(String, nullable=True)
    location: Mapped[EventLocationEnum] = mapped_column(String, nullable=True)  # EventLocationEnum
    location_details: Mapped[str] = mapped_column(String, nullable=True)

    # Artificial-insemination detail.
    ai_technician_name: Mapped[str] = mapped_column(String, nullable=True)
    ai_technique: Mapped[str] = mapped_column(String, nullable=True)
    semen_batch_number: Mapped[str] = mapped_column(String, nullable=True)

    expected_calving_date: Mapped[str] = mapped_column(Date, nullable=True)
    pregnancy_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=True)
    pregnancy_confirmation_date: Mapped[str] = mapped_column(Date, nullable=True)
    outcome: Mapped[BreedingOutcomeEnum] = mapped_column(String, nullable=True)  # BreedingOutcomeEnum
    notes: Mapped[str] = mapped_column(Text, nullable=True)


# All Register classes should have the prefix G2PRegister
class G2PRegisterBreeding(G2PRegister, G2PBreeding):
    __tablename__ = "g2p_register_breedings"

    def get_search_text_fields(self) -> str:
        """Return breeding fields used to build search_text."""
        return G2PRegisterDomainServiceBreeding().construct_search_text(self.to_dict())

    def get_record_name_fields(self) -> str:
        """Return breeding record_name from domain service implementation."""
        return G2PRegisterDomainServiceBreeding().construct_record_name(self.to_dict())


# All Register History classes should have the prefix G2PRegisterHistory
class G2PRegisterHistoryBreeding(G2PRegisterHistory, G2PBreeding):
    __tablename__ = "g2p_register_history_breedings"


# All Intake Form classes should have the prefix G2PIntakeForm
class G2PIntakeFormBreeding(G2PIntakeForm, G2PRegister, G2PBreeding):
    __tablename__ = "g2p_intake_form_breedings"

    async def get_link_internal_record_id(self, session):
        from .livestock import G2PIntakeFormLivestock
        result = await session.execute(
            select(G2PIntakeFormLivestock).where(
                G2PIntakeFormLivestock.submission_id == self.submission_id
            )
        )
        livestock = result.scalars().first()
        if livestock:
            self.link_internal_record_id = livestock.internal_record_id

    def get_search_text_fields(self) -> str:
        """Return breeding fields used to build search_text."""
        return G2PRegisterDomainServiceBreeding().construct_search_text(self.to_dict())

    def get_record_name_fields(self) -> str:
        """Return breeding record_name from domain service implementation."""
        return G2PRegisterDomainServiceBreeding().construct_record_name(self.to_dict())
