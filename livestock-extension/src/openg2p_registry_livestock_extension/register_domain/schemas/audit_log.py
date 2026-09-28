from datetime import datetime
from typing import Optional

from openg2p_registry_core.schemas import (
    G2PRegisterBaseSchema,
    G2PRegisterHistorySchema,
    G2PIntakeFormSchemaBase,
)
from ..models.enums import AuditActionTypeEnum


class G2PSchemaAuditLog:

    res_model: Optional[str] = None
    res_record_id: Optional[int] = None
    action_type: Optional[AuditActionTypeEnum] = None
    user_name: Optional[str] = None
    user_role: Optional[str] = None
    changes: Optional[str] = None
    event_timestamp: Optional[datetime] = None
    ip_address: Optional[str] = None
    session_id: Optional[str] = None


class G2PRegisterSchemaAuditLog(G2PRegisterBaseSchema, G2PSchemaAuditLog):
    """
    Schema for Audit Log register.
    Inherits fields from G2PRegisterBaseSchema.
    Attributes inherited from G2PSchemaAuditLog are specific to the Audit Log domain.
    """


class G2PRegisterHistorySchemaAuditLog(G2PRegisterHistorySchema):
    """
    Schema for Audit Log history.
    Inherits fields from G2PRegisterHistorySchema.
    """


class G2PIntakeFormSchemaAuditLog(G2PIntakeFormSchemaBase, G2PRegisterBaseSchema, G2PSchemaAuditLog):
    """
    Schema for Audit Log intake form.
    Inherits fields from G2PRegisterBaseSchema.
    Attributes inherited from G2PSchemaAuditLog are specific to the Audit Log domain and are
    included in the intake form schema for data collection.
    """
