"""VITAL EVENT lines — a child of LIVESTOCK.

Mirrors `g2p.livestock.vital.event`: births, mortalities and notifiable disease
episodes. The Odoo model overloads this record with the diagnosis fields for the
`disease` type and the offspring fields for `birth`, and both sets are kept here so a
single table still covers all three event types.
"""

from openg2p_registry_core.models.g2p_intake_form import G2PIntakeForm
from openg2p_registry_core.models import G2PRegister, G2PRegisterHistory
from sqlalchemy import Boolean, Date, Integer, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from ..services import G2PRegisterDomainServiceVitalEvent
from .enums import EventLocationEnum, VitalEventCauseEnum, VitalEventTypeEnum


class G2PVitalEvent:

    ear_tag_id: Mapped[str] = mapped_column(String, nullable=True)
    species: Mapped[str] = mapped_column(String, nullable=True)  # Attribute lookup (LIVESTOCK_SPECIES)
    event_type: Mapped[VitalEventTypeEnum] = mapped_column(String, nullable=True)  # VitalEventTypeEnum
    event_date: Mapped[str] = mapped_column(Date, nullable=True)
    cause: Mapped[VitalEventCauseEnum] = mapped_column(String, nullable=True)  # VitalEventCauseEnum
    location: Mapped[EventLocationEnum] = mapped_column(String, nullable=True)  # EventLocationEnum
    location_details: Mapped[str] = mapped_column(String, nullable=True)

    # Disease-type detail.
    disease_type: Mapped[str] = mapped_column(String, nullable=True)  # Attribute lookup (LIVESTOCK_DISEASE)
    date_onset: Mapped[str] = mapped_column(Date, nullable=True)
    date_resolution: Mapped[str] = mapped_column(Date, nullable=True)
    treatment: Mapped[str] = mapped_column(Text, nullable=True)
    veterinarian_name: Mapped[str] = mapped_column(String, nullable=True)
    is_notifiable: Mapped[bool] = mapped_column(Boolean, nullable=True)

    # Birth-type detail.
    offspring_count: Mapped[int] = mapped_column(Integer, nullable=True)
    offspring_ear_tag_prefix: Mapped[str] = mapped_column(String, nullable=True)

    reporting_officer: Mapped[str] = mapped_column(String, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)


# All Register classes should have the prefix G2PRegister
class G2PRegisterVitalEvent(G2PRegister, G2PVitalEvent):
    __tablename__ = "g2p_register_vital_events"

    def get_search_text_fields(self) -> str:
        """Return vital event fields used to build search_text."""
        return G2PRegisterDomainServiceVitalEvent().construct_search_text(self.to_dict())

    def get_record_name_fields(self) -> str:
        """Return vital event record_name from domain service implementation."""
        return G2PRegisterDomainServiceVitalEvent().construct_record_name(self.to_dict())


# All Register History classes should have the prefix G2PRegisterHistory
class G2PRegisterHistoryVitalEvent(G2PRegisterHistory, G2PVitalEvent):
    __tablename__ = "g2p_register_history_vital_events"


# All Intake Form classes should have the prefix G2PIntakeForm
class G2PIntakeFormVitalEvent(G2PIntakeForm, G2PRegister, G2PVitalEvent):
    __tablename__ = "g2p_intake_form_vital_events"

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
        """Return vital event fields used to build search_text."""
        return G2PRegisterDomainServiceVitalEvent().construct_search_text(self.to_dict())

    def get_record_name_fields(self) -> str:
        """Return vital event record_name from domain service implementation."""
        return G2PRegisterDomainServiceVitalEvent().construct_record_name(self.to_dict())
