"""IMPORT BATCH lines — a child of LIVESTOCK.

Mirrors `g2p.livestock.import.batch`: one row per bulk load from an upstream system
(DOVAR, LITS, Case Book, ALIVE) with the row counts and error log that make a partial
import auditable. The file itself lives in object storage, referenced by
`import_file_document_id`, rather than as a binary column.
"""

from openg2p_registry_core.models.g2p_intake_form import G2PIntakeForm
from openg2p_registry_core.models import G2PRegister, G2PRegisterHistory
from sqlalchemy import DateTime, Integer, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from ..services import G2PRegisterDomainServiceImportBatch
from .enums import ImportSourceSystemEnum, ImportStateEnum


class G2PImportBatch:

    batch_reference: Mapped[str] = mapped_column(String, nullable=True)
    source_system: Mapped[ImportSourceSystemEnum] = mapped_column(String, nullable=True)  # ImportSourceSystemEnum
    state: Mapped[ImportStateEnum] = mapped_column(String, nullable=True)  # ImportStateEnum
    import_filename: Mapped[str] = mapped_column(String, nullable=True)
    import_file_document_id: Mapped[str] = mapped_column(String, nullable=True)
    total_rows: Mapped[int] = mapped_column(Integer, nullable=True)
    success_count: Mapped[int] = mapped_column(Integer, nullable=True)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=True)
    conflict_count: Mapped[int] = mapped_column(Integer, nullable=True)
    error_log: Mapped[str] = mapped_column(Text, nullable=True)
    processed_by: Mapped[str] = mapped_column(String, nullable=True)
    processing_date: Mapped[str] = mapped_column(DateTime, nullable=True)


# All Register classes should have the prefix G2PRegister
class G2PRegisterImportBatch(G2PRegister, G2PImportBatch):
    __tablename__ = "g2p_register_import_batches"

    def get_search_text_fields(self) -> str:
        """Return import batch fields used to build search_text."""
        return G2PRegisterDomainServiceImportBatch().construct_search_text(self.to_dict())

    def get_record_name_fields(self) -> str:
        """Return import batch record_name from domain service implementation."""
        return G2PRegisterDomainServiceImportBatch().construct_record_name(self.to_dict())


# All Register History classes should have the prefix G2PRegisterHistory
class G2PRegisterHistoryImportBatch(G2PRegisterHistory, G2PImportBatch):
    __tablename__ = "g2p_register_history_import_batches"


# All Intake Form classes should have the prefix G2PIntakeForm
class G2PIntakeFormImportBatch(G2PIntakeForm, G2PRegister, G2PImportBatch):
    __tablename__ = "g2p_intake_form_import_batches"

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
        """Return import batch fields used to build search_text."""
        return G2PRegisterDomainServiceImportBatch().construct_search_text(self.to_dict())

    def get_record_name_fields(self) -> str:
        """Return import batch record_name from domain service implementation."""
        return G2PRegisterDomainServiceImportBatch().construct_record_name(self.to_dict())
