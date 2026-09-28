"""AUDIT LOG lines — a child of LIVESTOCK.

Mirrors `g2p.livestock.audit.log`: the module's own immutable trail of who changed
what, kept because the SRS requires an operator-visible log with the acting role, IP
and session recorded alongside the change.

Note this sits alongside, not instead of, the platform's own `g2p_register_history_*`
tables. Those version the record; this records the actor and the context.
"""

from openg2p_registry_core.models.g2p_intake_form import G2PIntakeForm
from openg2p_registry_core.models import G2PRegister, G2PRegisterHistory
from sqlalchemy import DateTime, Integer, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from ..services import G2PRegisterDomainServiceAuditLog
from .enums import AuditActionTypeEnum


class G2PAuditLog:

    res_model: Mapped[str] = mapped_column(String, nullable=True)
    res_record_id: Mapped[int] = mapped_column(Integer, nullable=True)
    action_type: Mapped[AuditActionTypeEnum] = mapped_column(String, nullable=True)  # AuditActionTypeEnum
    user_name: Mapped[str] = mapped_column(String, nullable=True)
    user_role: Mapped[str] = mapped_column(String, nullable=True)
    changes: Mapped[str] = mapped_column(Text, nullable=True)
    event_timestamp: Mapped[str] = mapped_column(DateTime, nullable=True)
    ip_address: Mapped[str] = mapped_column(String, nullable=True)
    session_id: Mapped[str] = mapped_column(String, nullable=True)


# All Register classes should have the prefix G2PRegister
class G2PRegisterAuditLog(G2PRegister, G2PAuditLog):
    __tablename__ = "g2p_register_audit_logs"

    def get_search_text_fields(self) -> str:
        """Return audit log fields used to build search_text."""
        return G2PRegisterDomainServiceAuditLog().construct_search_text(self.to_dict())

    def get_record_name_fields(self) -> str:
        """Return audit log record_name from domain service implementation."""
        return G2PRegisterDomainServiceAuditLog().construct_record_name(self.to_dict())


# All Register History classes should have the prefix G2PRegisterHistory
class G2PRegisterHistoryAuditLog(G2PRegisterHistory, G2PAuditLog):
    __tablename__ = "g2p_register_history_audit_logs"


# All Intake Form classes should have the prefix G2PIntakeForm
class G2PIntakeFormAuditLog(G2PIntakeForm, G2PRegister, G2PAuditLog):
    __tablename__ = "g2p_intake_form_audit_logs"

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
        """Return audit log fields used to build search_text."""
        return G2PRegisterDomainServiceAuditLog().construct_search_text(self.to_dict())

    def get_record_name_fields(self) -> str:
        """Return audit log record_name from domain service implementation."""
        return G2PRegisterDomainServiceAuditLog().construct_record_name(self.to_dict())
