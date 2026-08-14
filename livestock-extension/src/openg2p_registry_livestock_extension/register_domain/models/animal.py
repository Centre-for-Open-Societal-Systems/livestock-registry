"""ANIMAL lines — a child of LIVESTOCK.

Mirrors `g2p.livestock.registry.line`: the individual animal profile carrying the ear
tag that makes it traceable. Species and breed are attribute lookups so the catalogue
can grow without a migration; sex, health and vaccination status are closed sets.
"""

from openg2p_registry_core.models.g2p_intake_form import G2PIntakeForm
from openg2p_registry_core.models import G2PRegister, G2PRegisterHistory
from sqlalchemy import Date, Numeric, String, select
from sqlalchemy.orm import Mapped, mapped_column

from ..services import G2PRegisterDomainServiceAnimal
from .enums import (
    AnimalStateEnum, GenderEnum, HealthStatusEnum, VaccinationStatusEnum,
)


class G2PAnimal:

    ear_tag_id: Mapped[str] = mapped_column(String, nullable=True)
    secondary_identifier: Mapped[str] = mapped_column(String, nullable=True)
    animal_name: Mapped[str] = mapped_column(String, nullable=True)
    species: Mapped[str] = mapped_column(String, nullable=True)   # Attribute lookup (LIVESTOCK_SPECIES)
    breed: Mapped[str] = mapped_column(String, nullable=True)     # Attribute lookup (LIVESTOCK_BREED)
    gender: Mapped[GenderEnum] = mapped_column(String, nullable=True)  # GenderEnum
    date_of_birth: Mapped[str] = mapped_column(Date, nullable=True)
    age: Mapped[str] = mapped_column(String, nullable=True)
    weight: Mapped[float] = mapped_column(Numeric, nullable=True)
    health_status: Mapped[HealthStatusEnum] = mapped_column(String, nullable=True)  # HealthStatusEnum
    vaccination_status: Mapped[VaccinationStatusEnum] = mapped_column(String, nullable=True)  # VaccinationStatusEnum
    registration_date: Mapped[str] = mapped_column(Date, nullable=True)
    state: Mapped[AnimalStateEnum] = mapped_column(String, nullable=True)  # AnimalStateEnum


# All Register classes should have the prefix G2PRegister
class G2PRegisterAnimal(G2PRegister, G2PAnimal):
    __tablename__ = "g2p_register_animals"

    def get_search_text_fields(self) -> str:
        """Return animal fields used to build search_text."""
        return G2PRegisterDomainServiceAnimal().construct_search_text(self.to_dict())

    def get_record_name_fields(self) -> str:
        """Return animal record_name from domain service implementation."""
        return G2PRegisterDomainServiceAnimal().construct_record_name(self.to_dict())


# All Register History classes should have the prefix G2PRegisterHistory
class G2PRegisterHistoryAnimal(G2PRegisterHistory, G2PAnimal):
    __tablename__ = "g2p_register_history_animals"


# All Intake Form classes should have the prefix G2PIntakeForm
class G2PIntakeFormAnimal(G2PIntakeForm, G2PRegister, G2PAnimal):
    __tablename__ = "g2p_intake_form_animals"

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
        """Return animal fields used to build search_text."""
        return G2PRegisterDomainServiceAnimal().construct_search_text(self.to_dict())

    def get_record_name_fields(self) -> str:
        """Return animal record_name from domain service implementation."""
        return G2PRegisterDomainServiceAnimal().construct_record_name(self.to_dict())
