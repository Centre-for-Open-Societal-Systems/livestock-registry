"""HEALTH EVENT lines — a child of LIVESTOCK.

Mirrors `g2p.livestock.health.event`: disease, injury, treatment and recovery episodes
recorded against an animal. The animal is named by `ear_tag_id` rather than a foreign
key, matching how the other lines reference their subject.
"""

from openg2p_registry_core.models.g2p_intake_form import G2PIntakeForm
from openg2p_registry_core.models import G2PRegister, G2PRegisterHistory
from sqlalchemy import Boolean, Date, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from ..services import G2PRegisterDomainServiceHealthEvent
from .enums import EventLocationEnum, HealthEventTypeEnum


class G2PHealthEvent:

    ear_tag_id: Mapped[str] = mapped_column(String, nullable=True)
    species: Mapped[str] = mapped_column(String, nullable=True)  # Attribute lookup (LIVESTOCK_SPECIES)
    event_type: Mapped[HealthEventTypeEnum] = mapped_column(String, nullable=True)  # HealthEventTypeEnum
    disease_type: Mapped[str] = mapped_column(String, nullable=True)  # Attribute lookup (LIVESTOCK_DISEASE)
    date_onset: Mapped[str] = mapped_column(Date, nullable=True)
    date_resolution: Mapped[str] = mapped_column(Date, nullable=True)
    treatment: Mapped[str] = mapped_column(Text, nullable=True)
    veterinarian_name: Mapped[str] = mapped_column(String, nullable=True)
    location: Mapped[EventLocationEnum] = mapped_column(String, nullable=True)  # EventLocationEnum
    location_details: Mapped[str] = mapped_column(String, nullable=True)
    is_notifiable: Mapped[bool] = mapped_column(Boolean, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)


# All Register classes should have the prefix G2PRegister
class G2PRegisterHealthEvent(G2PRegister, G2PHealthEvent):
    __tablename__ = "g2p_register_health_events"

    def get_search_text_fields(self) -> str:
        """Return health event fields used to build search_text."""
        return G2PRegisterDomainServiceHealthEvent().construct_search_text(self.to_dict())

    def get_record_name_fields(self) -> str:
        """Return health event record_name from domain service implementation."""
        return G2PRegisterDomainServiceHealthEvent().construct_record_name(self.to_dict())


# All Register History classes should have the prefix G2PRegisterHistory
class G2PRegisterHistoryHealthEvent(G2PRegisterHistory, G2PHealthEvent):
    __tablename__ = "g2p_register_history_health_events"


# All Intake Form classes should have the prefix G2PIntakeForm
class G2PIntakeFormHealthEvent(G2PIntakeForm, G2PRegister, G2PHealthEvent):
    __tablename__ = "g2p_intake_form_health_events"

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
        """Return health event fields used to build search_text."""
        return G2PRegisterDomainServiceHealthEvent().construct_search_text(self.to_dict())

    def get_record_name_fields(self) -> str:
        """Return health event record_name from domain service implementation."""
        return G2PRegisterDomainServiceHealthEvent().construct_record_name(self.to_dict())
