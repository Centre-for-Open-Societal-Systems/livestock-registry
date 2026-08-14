from datetime import date
from typing import Optional

from openg2p_registry_core.schemas import (
    G2PRegisterBaseSchema,
    G2PRegisterHistorySchema,
    G2PIntakeFormSchemaBase,
)
from ..models.enums import BreedingEventTypeEnum, BreedingOutcomeEnum, EventLocationEnum


class G2PSchemaBreeding:

    ear_tag_id: Optional[str] = None
    species: Optional[str] = None
    event_type: Optional[BreedingEventTypeEnum] = None
    breeding_date: Optional[date] = None
    sire_or_semen_id: Optional[str] = None
    location: Optional[EventLocationEnum] = None
    location_details: Optional[str] = None
    ai_technician_name: Optional[str] = None
    ai_technique: Optional[str] = None
    semen_batch_number: Optional[str] = None
    expected_calving_date: Optional[date] = None
    pregnancy_confirmed: Optional[bool] = None
    pregnancy_confirmation_date: Optional[date] = None
    outcome: Optional[BreedingOutcomeEnum] = None
    notes: Optional[str] = None


class G2PRegisterSchemaBreeding(G2PRegisterBaseSchema, G2PSchemaBreeding):
    """
    Schema for Breeding register.
    Inherits fields from G2PRegisterBaseSchema.
    Attributes inherited from G2PSchemaBreeding are specific to the Breeding domain.
    """


class G2PRegisterHistorySchemaBreeding(G2PRegisterHistorySchema):
    """
    Schema for Breeding history.
    Inherits fields from G2PRegisterHistorySchema.
    """


class G2PIntakeFormSchemaBreeding(G2PIntakeFormSchemaBase, G2PRegisterBaseSchema, G2PSchemaBreeding):
    """
    Schema for Breeding intake form.
    Inherits fields from G2PRegisterBaseSchema.
    Attributes inherited from G2PSchemaBreeding are specific to the Breeding domain and are
    included in the intake form schema for data collection.
    """
