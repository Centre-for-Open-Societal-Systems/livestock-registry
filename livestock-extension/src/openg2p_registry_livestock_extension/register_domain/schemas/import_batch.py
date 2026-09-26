from datetime import datetime
from typing import Optional

from openg2p_registry_core.schemas import (
    G2PRegisterBaseSchema,
    G2PRegisterHistorySchema,
    G2PIntakeFormSchemaBase,
)
from ..models.enums import ImportSourceSystemEnum, ImportStateEnum


class G2PSchemaImportBatch:

    batch_reference: Optional[str] = None
    source_system: Optional[ImportSourceSystemEnum] = None
    state: Optional[ImportStateEnum] = None
    import_filename: Optional[str] = None
    import_file_document_id: Optional[str] = None
    total_rows: Optional[int] = None
    success_count: Optional[int] = None
    failure_count: Optional[int] = None
    conflict_count: Optional[int] = None
    error_log: Optional[str] = None
    processed_by: Optional[str] = None
    processing_date: Optional[datetime] = None


class G2PRegisterSchemaImportBatch(G2PRegisterBaseSchema, G2PSchemaImportBatch):
    """
    Schema for Import Batch register.
    Inherits fields from G2PRegisterBaseSchema.
    Attributes inherited from G2PSchemaImportBatch are specific to the Import Batch domain.
    """


class G2PRegisterHistorySchemaImportBatch(G2PRegisterHistorySchema):
    """
    Schema for Import Batch history.
    Inherits fields from G2PRegisterHistorySchema.
    """


class G2PIntakeFormSchemaImportBatch(G2PIntakeFormSchemaBase, G2PRegisterBaseSchema, G2PSchemaImportBatch):
    """
    Schema for Import Batch intake form.
    Inherits fields from G2PRegisterBaseSchema.
    Attributes inherited from G2PSchemaImportBatch are specific to the Import Batch domain and are
    included in the intake form schema for data collection.
    """
