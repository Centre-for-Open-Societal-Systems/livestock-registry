from datetime import date
from typing import Optional

from openg2p_registry_core.schemas import (
    G2PRegisterBaseSchema,
    G2PRegisterHistorySchema,
    G2PIntakeFormSchemaBase,
)
from ..models.enums import AnimalStateEnum, GenderEnum, HealthStatusEnum, VaccinationStatusEnum


class G2PSchemaAnimal:

    ear_tag_id: Optional[str] = None
    secondary_identifier: Optional[str] = None
    animal_name: Optional[str] = None
    species: Optional[str] = None
    breed: Optional[str] = None
    gender: Optional[GenderEnum] = None
    date_of_birth: Optional[date] = None
    age: Optional[str] = None
    weight: Optional[float] = None
    health_status: Optional[HealthStatusEnum] = None
    vaccination_status: Optional[VaccinationStatusEnum] = None
    registration_date: Optional[date] = None
    state: Optional[AnimalStateEnum] = None


class G2PRegisterSchemaAnimal(G2PRegisterBaseSchema, G2PSchemaAnimal):
    """
    Schema for Animal register.
    Inherits fields from G2PRegisterBaseSchema.
    Attributes inherited from G2PSchemaAnimal are specific to the Animal domain.
    """


class G2PRegisterHistorySchemaAnimal(G2PRegisterHistorySchema):
    """
    Schema for Animal history.
    Inherits fields from G2PRegisterHistorySchema.
    """


class G2PIntakeFormSchemaAnimal(G2PIntakeFormSchemaBase, G2PRegisterBaseSchema, G2PSchemaAnimal):
    """
    Schema for Animal intake form.
    Inherits fields from G2PRegisterBaseSchema.
    Attributes inherited from G2PSchemaAnimal are specific to the Animal domain and are
    included in the intake form schema for data collection.
    """
