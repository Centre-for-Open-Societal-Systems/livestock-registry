"""VACCINE SCHEDULE lines — a child of LIVESTOCK.

Mirrors `g2p.livestock.vaccine.schedule`: the vaccine, the species it applies to, and
the interval in days that drives a vaccination's `next_due_date`. Kept as a register
line rather than a pure catalogue because the interval is operational data a registry
administrator tunes, not a value the master-data service owns.
"""

from openg2p_registry_core.models.g2p_intake_form import G2PIntakeForm
from openg2p_registry_core.models import G2PRegister, G2PRegisterHistory
from sqlalchemy import Boolean, Integer, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from ..services import G2PRegisterDomainServiceVaccineSchedule


class G2PVaccineSchedule:

    vaccine_name: Mapped[str] = mapped_column(String, nullable=True)  # Attribute lookup (VACCINE_TYPE)
    species: Mapped[str] = mapped_column(String, nullable=True)       # Attribute lookup (LIVESTOCK_SPECIES)
    interval_days: Mapped[int] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)


# All Register classes should have the prefix G2PRegister
class G2PRegisterVaccineSchedule(G2PRegister, G2PVaccineSchedule):
    __tablename__ = "g2p_register_vaccine_schedules"

    def get_search_text_fields(self) -> str:
        """Return vaccine schedule fields used to build search_text."""
        return G2PRegisterDomainServiceVaccineSchedule().construct_search_text(self.to_dict())

    def get_record_name_fields(self) -> str:
        """Return vaccine schedule record_name from domain service implementation."""
        return G2PRegisterDomainServiceVaccineSchedule().construct_record_name(self.to_dict())


# All Register History classes should have the prefix G2PRegisterHistory
class G2PRegisterHistoryVaccineSchedule(G2PRegisterHistory, G2PVaccineSchedule):
    __tablename__ = "g2p_register_history_vaccine_schedules"


# All Intake Form classes should have the prefix G2PIntakeForm
class G2PIntakeFormVaccineSchedule(G2PIntakeForm, G2PRegister, G2PVaccineSchedule):
    __tablename__ = "g2p_intake_form_vaccine_schedules"

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
        """Return vaccine schedule fields used to build search_text."""
        return G2PRegisterDomainServiceVaccineSchedule().construct_search_text(self.to_dict())

    def get_record_name_fields(self) -> str:
        """Return vaccine schedule record_name from domain service implementation."""
        return G2PRegisterDomainServiceVaccineSchedule().construct_record_name(self.to_dict())
