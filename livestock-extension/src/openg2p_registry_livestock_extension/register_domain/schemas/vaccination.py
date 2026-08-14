from datetime import date
from typing import Optional

from openg2p_registry_core.schemas import (
    G2PRegisterBaseSchema,
    G2PRegisterHistorySchema,
    G2PIntakeFormSchemaBase,
)


class G2PSchemaVaccination:

    ear_tag_id: Optional[str] = None
    species: Optional[str] = None
    vaccine_type: Optional[str] = None
    vaccination_date: Optional[date] = None
    next_due_date: Optional[date] = None
    batch_number: Optional[str] = None
    administered_by: Optional[str] = None
    notes: Optional[str] = None


class G2PRegisterSchemaVaccination(G2PRegisterBaseSchema, G2PSchemaVaccination):
    """
    Schema for Vaccination register.
    Inherits fields from G2PRegisterBaseSchema.
    Attributes inherited from G2PSchemaVaccination are specific to the Vaccination domain.
    """


class G2PRegisterHistorySchemaVaccination(G2PRegisterHistorySchema):
    """
    Schema for Vaccination history.
    Inherits fields from G2PRegisterHistorySchema.
    """


class G2PIntakeFormSchemaVaccination(G2PIntakeFormSchemaBase, G2PRegisterBaseSchema, G2PSchemaVaccination):
    """
    Schema for Vaccination intake form.
    Inherits fields from G2PRegisterBaseSchema.
    Attributes inherited from G2PSchemaVaccination are specific to the Vaccination domain and are
    included in the intake form schema for data collection.
    """
