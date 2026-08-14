from datetime import date
from typing import Optional

from openg2p_registry_core.schemas import (
    G2PRegisterBaseSchema,
    G2PRegisterHistorySchema,
    G2PIntakeFormSchemaBase,
)
from ..models.enums import EventLocationEnum, HealthEventTypeEnum


class G2PSchemaHealthEvent:

    ear_tag_id: Optional[str] = None
    species: Optional[str] = None
    event_type: Optional[HealthEventTypeEnum] = None
    disease_type: Optional[str] = None
    date_onset: Optional[date] = None
    date_resolution: Optional[date] = None
    treatment: Optional[str] = None
    veterinarian_name: Optional[str] = None
    location: Optional[EventLocationEnum] = None
    location_details: Optional[str] = None
    is_notifiable: Optional[bool] = None
    notes: Optional[str] = None


class G2PRegisterSchemaHealthEvent(G2PRegisterBaseSchema, G2PSchemaHealthEvent):
    """
    Schema for Health Event register.
    Inherits fields from G2PRegisterBaseSchema.
    Attributes inherited from G2PSchemaHealthEvent are specific to the Health Event domain.
    """


class G2PRegisterHistorySchemaHealthEvent(G2PRegisterHistorySchema):
    """
    Schema for Health Event history.
    Inherits fields from G2PRegisterHistorySchema.
    """


class G2PIntakeFormSchemaHealthEvent(G2PIntakeFormSchemaBase, G2PRegisterBaseSchema, G2PSchemaHealthEvent):
    """
    Schema for Health Event intake form.
    Inherits fields from G2PRegisterBaseSchema.
    Attributes inherited from G2PSchemaHealthEvent are specific to the Health Event domain and are
    included in the intake form schema for data collection.
    """
