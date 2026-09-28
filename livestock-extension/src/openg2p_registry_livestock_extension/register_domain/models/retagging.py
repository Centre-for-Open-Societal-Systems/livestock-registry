"""RETAGGING lines — a child of LIVESTOCK.

SRS LR-03 / LR-14: an animal whose ear tag is lost, damaged or upgraded gets a
new tag. One row per replacement, kept forever as the permanent old -> new
link; the animal itself keeps its record (and OAN/internal id) and only its
ear_tag_id changes, once the change request that adds this row is approved
(G2PRegisterDomainServiceRetagging.post_approve).

`ear_tag_id` is the ORIGINAL tag — named like every other event line's animal
reference so the event-dialog tooling treats it the same way.
"""

from openg2p_registry_core.models.g2p_intake_form import G2PIntakeForm
from openg2p_registry_core.models import G2PRegister, G2PRegisterHistory
from sqlalchemy import Date, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from ..services import G2PRegisterDomainServiceRetagging
from .enums import RetagReasonEnum


class G2PRetagging:

    ear_tag_id: Mapped[str] = mapped_column(String, nullable=True)  # original tag
    species: Mapped[str] = mapped_column(String, nullable=True)  # Attribute lookup (LIVESTOCK_SPECIES), from the animal
    new_ear_tag_id: Mapped[str] = mapped_column(String, nullable=True)
    reason: Mapped[RetagReasonEnum] = mapped_column(String, nullable=True)  # RetagReasonEnum
    retag_date: Mapped[str] = mapped_column(Date, nullable=True)
    approving_officer: Mapped[str] = mapped_column(String, nullable=True)
    justification: Mapped[str] = mapped_column(Text, nullable=True)
    # Set by post_approve once the animal (and its event lines) carry the new
    # tag; NULL means approved-but-not-yet-applied, which never survives a
    # committed approval (post_approve raises and the approval rolls back).
    applied_on: Mapped[str] = mapped_column(Date, nullable=True)


# All Register classes should have the prefix G2PRegister
class G2PRegisterRetagging(G2PRegister, G2PRetagging):
    __tablename__ = "g2p_register_retaggings"

    def get_search_text_fields(self) -> str:
        """Return retagging fields used to build search_text."""
        return G2PRegisterDomainServiceRetagging().construct_search_text(self.to_dict())

    def get_record_name_fields(self) -> str:
        """Return retagging record_name from domain service implementation."""
        return G2PRegisterDomainServiceRetagging().construct_record_name(self.to_dict())


# All Register History classes should have the prefix G2PRegisterHistory
class G2PRegisterHistoryRetagging(G2PRegisterHistory, G2PRetagging):
    __tablename__ = "g2p_register_history_retaggings"


# All Intake Form classes should have the prefix G2PIntakeForm
class G2PIntakeFormRetagging(G2PIntakeForm, G2PRegister, G2PRetagging):
    __tablename__ = "g2p_intake_form_retaggings"

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
        """Return retagging fields used to build search_text."""
        return G2PRegisterDomainServiceRetagging().construct_search_text(self.to_dict())

    def get_record_name_fields(self) -> str:
        """Return retagging record_name from domain service implementation."""
        return G2PRegisterDomainServiceRetagging().construct_record_name(self.to_dict())
