"""VACCINATION lines — a child of LIVESTOCK.

Mirrors `g2p.livestock.vaccination`. `next_due_date` is computed in the Odoo module
from the vaccine schedule's interval; it is stored here so the overdue reminders can
be driven straight off the register without recomputing.
"""

from openg2p_registry_core.models.g2p_intake_form import G2PIntakeForm
from openg2p_registry_core.models import G2PRegister, G2PRegisterHistory
from sqlalchemy import Date, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from ..services import G2PRegisterDomainServiceVaccination


class G2PVaccination:

    ear_tag_id: Mapped[str] = mapped_column(String, nullable=True)
    species: Mapped[str] = mapped_column(String, nullable=True)  # Attribute lookup (LIVESTOCK_SPECIES)
    vaccine_type: Mapped[str] = mapped_column(String, nullable=True)  # Attribute lookup (VACCINE_TYPE)
    vaccination_date: Mapped[str] = mapped_column(Date, nullable=True)
    next_due_date: Mapped[str] = mapped_column(Date, nullable=True)
    batch_number: Mapped[str] = mapped_column(String, nullable=True)
    administered_by: Mapped[str] = mapped_column(String, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)


# All Register classes should have the prefix G2PRegister
class G2PRegisterVaccination(G2PRegister, G2PVaccination):
    __tablename__ = "g2p_register_vaccinations"

    def get_search_text_fields(self) -> str:
        """Return vaccination fields used to build search_text."""
        return G2PRegisterDomainServiceVaccination().construct_search_text(self.to_dict())

    def get_record_name_fields(self) -> str:
        """Return vaccination record_name from domain service implementation."""
        return G2PRegisterDomainServiceVaccination().construct_record_name(self.to_dict())


# All Register History classes should have the prefix G2PRegisterHistory
class G2PRegisterHistoryVaccination(G2PRegisterHistory, G2PVaccination):
    __tablename__ = "g2p_register_history_vaccinations"


# All Intake Form classes should have the prefix G2PIntakeForm
class G2PIntakeFormVaccination(G2PIntakeForm, G2PRegister, G2PVaccination):
    __tablename__ = "g2p_intake_form_vaccinations"

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
        """Return vaccination fields used to build search_text."""
        return G2PRegisterDomainServiceVaccination().construct_search_text(self.to_dict())

    def get_record_name_fields(self) -> str:
        """Return vaccination record_name from domain service implementation."""
        return G2PRegisterDomainServiceVaccination().construct_record_name(self.to_dict())
