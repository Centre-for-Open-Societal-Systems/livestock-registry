from datetime import date
from typing import Optional

from openg2p_registry_core.schemas import (
    G2PRegisterBaseSchema,
    G2PRegisterHistorySchema,
    G2PIntakeFormSchemaBase,
)
from ..models.enums import EventLocationEnum, VitalEventCauseEnum, VitalEventTypeEnum


class G2PSchemaVitalEvent:

    ear_tag_id: Optional[str] = None
    species: Optional[str] = None
    event_type: Optional[VitalEventTypeEnum] = None
    event_date: Optional[date] = None
    cause: Optional[VitalEventCauseEnum] = None
    location: Optional[EventLocationEnum] = None
    location_details: Optional[str] = None
    disease_type: Optional[str] = None
    date_onset: Optional[date] = None
    date_resolution: Optional[date] = None
    treatment: Optional[str] = None
    veterinarian_name: Optional[str] = None
    is_notifiable: Optional[bool] = None
    offspring_count: Optional[int] = None
    offspring_ear_tag_prefix: Optional[str] = None
    reporting_officer: Optional[str] = None
    notes: Optional[str] = None


class G2PRegisterSchemaVitalEvent(G2PRegisterBaseSchema, G2PSchemaVitalEvent):
    """
    Schema for Vital Event register.
    Inherits fields from G2PRegisterBaseSchema.
    Attributes inherited from G2PSchemaVitalEvent are specific to the Vital Event domain.
    """


class G2PRegisterHistorySchemaVitalEvent(G2PRegisterHistorySchema):
    """
    Schema for Vital Event history.
    Inherits fields from G2PRegisterHistorySchema.
    """


class G2PIntakeFormSchemaVitalEvent(G2PIntakeFormSchemaBase, G2PRegisterBaseSchema, G2PSchemaVitalEvent):
    """
    Schema for Vital Event intake form.
    Inherits fields from G2PRegisterBaseSchema.
    Attributes inherited from G2PSchemaVitalEvent are specific to the Vital Event domain and are
    included in the intake form schema for data collection.
    """
