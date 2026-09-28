from typing import Optional

from openg2p_registry_core.schemas import (
    G2PRegisterBaseSchema,
    G2PRegisterHistorySchema,
    G2PIntakeFormSchemaBase,
)


class G2PSchemaVaccineSchedule:

    vaccine_name: Optional[str] = None
    species: Optional[str] = None
    interval_days: Optional[int] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class G2PRegisterSchemaVaccineSchedule(G2PRegisterBaseSchema, G2PSchemaVaccineSchedule):
    """
    Schema for Vaccine Schedule register.
    Inherits fields from G2PRegisterBaseSchema.
    Attributes inherited from G2PSchemaVaccineSchedule are specific to the Vaccine Schedule domain.
    """


class G2PRegisterHistorySchemaVaccineSchedule(G2PRegisterHistorySchema):
    """
    Schema for Vaccine Schedule history.
    Inherits fields from G2PRegisterHistorySchema.
    """


class G2PIntakeFormSchemaVaccineSchedule(G2PIntakeFormSchemaBase, G2PRegisterBaseSchema, G2PSchemaVaccineSchedule):
    """
    Schema for Vaccine Schedule intake form.
    Inherits fields from G2PRegisterBaseSchema.
    Attributes inherited from G2PSchemaVaccineSchedule are specific to the Vaccine Schedule domain and are
    included in the intake form schema for data collection.
    """
