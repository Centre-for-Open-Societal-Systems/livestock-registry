from datetime import date
from typing import Optional

from openg2p_registry_core.schemas import (
    G2PRegisterBaseSchema,
    G2PRegisterHistorySchema,
    G2PIntakeFormSchemaBase,
)
from ..models.enums import RetagReasonEnum


class G2PSchemaRetagging:

    ear_tag_id: Optional[str] = None
    species: Optional[str] = None
    new_ear_tag_id: Optional[str] = None
    reason: Optional[RetagReasonEnum] = None
    retag_date: Optional[date] = None
    approving_officer: Optional[str] = None
    justification: Optional[str] = None
    applied_on: Optional[date] = None


class G2PRegisterSchemaRetagging(G2PRegisterBaseSchema, G2PSchemaRetagging):
    """
    Schema for Retagging register.
    Inherits fields from G2PRegisterBaseSchema.
    Attributes inherited from G2PSchemaRetagging are specific to the Retagging domain.
    """


class G2PRegisterHistorySchemaRetagging(G2PRegisterHistorySchema):
    """
    Schema for Retagging history.
    Inherits fields from G2PRegisterHistorySchema.
    """


class G2PIntakeFormSchemaRetagging(G2PIntakeFormSchemaBase, G2PRegisterBaseSchema, G2PSchemaRetagging):
    """
    Schema for Retagging intake form.
    Inherits fields from G2PRegisterBaseSchema.
    Attributes inherited from G2PSchemaRetagging are specific to the Retagging domain and are
    included in the intake form schema for data collection.
    """
