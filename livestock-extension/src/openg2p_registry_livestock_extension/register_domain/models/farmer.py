"""FARMER — the livestock keeper, held as a register in its own right.

This registry is not the system of record for farmers; the Farmer Registry is. What
is kept here is the identity needed to attach livestock to a person: the externally
issued Farmer ID and Fayda FAN, alongside the internally generated functional ID. The
Fayda FAN is mirrored into the platform's `link_foundational_id`, which exists for
exactly this "belongs to a person held elsewhere" case.
"""

from openg2p_registry_core.models.g2p_intake_form import G2PIntakeForm
from openg2p_registry_core.models import (
    G2PRegister, G2PRegisterHistory, G2PGeo, G2PGeoHistory
)
from sqlalchemy import JSON, Boolean, Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .admin_area import G2PAdminArea
from ..services import G2PRegisterDomainServiceFarmer


class G2PFarmer(G2PAdminArea):

    farmer_id: Mapped[str] = mapped_column(String, nullable=True)
    fayda_fan_id: Mapped[str] = mapped_column(String, nullable=True)
    fayda_fin: Mapped[str] = mapped_column(String, nullable=True)
    farmer_name: Mapped[str] = mapped_column(String, nullable=True)
    first_name: Mapped[str] = mapped_column(String, nullable=True)
    middle_name: Mapped[str] = mapped_column(String, nullable=True)
    last_name: Mapped[str] = mapped_column(String, nullable=True)
    first_name_amh: Mapped[str] = mapped_column(String, nullable=True)
    middle_name_amh: Mapped[str] = mapped_column(String, nullable=True)
    last_name_amh: Mapped[str] = mapped_column(String, nullable=True)
    first_name_other: Mapped[str] = mapped_column(String, nullable=True)
    middle_name_other: Mapped[str] = mapped_column(String, nullable=True)
    last_name_other: Mapped[str] = mapped_column(String, nullable=True)
    gender: Mapped[str] = mapped_column(String, nullable=True)
    date_of_birth: Mapped[str] = mapped_column(Date, nullable=True)
    mobile_number: Mapped[str] = mapped_column(String, nullable=True)
    email: Mapped[str] = mapped_column(String, nullable=True)
    region_name: Mapped[str] = mapped_column(String, nullable=True)
    zone_name: Mapped[str] = mapped_column(String, nullable=True)
    woreda_name: Mapped[str] = mapped_column(String, nullable=True)
    kebele_name: Mapped[str] = mapped_column(String, nullable=True)
    registration_date: Mapped[str] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=True)  # Attribute lookup (APPROVAL_STATUS)
    # ── The rest of the Farmer Registry's Farmer tab, under its own names ─────
    # (copied by the Farmer reference; the Fayda verification, documents and
    # staff names are not kept here). Latitude, longitude, altitude and plus
    # code are G2PGeo's columns.
    has_national_id: Mapped[bool] = mapped_column(Boolean, nullable=True)
    rid: Mapped[str] = mapped_column(String, nullable=True)
    odk_farmer_id: Mapped[str] = mapped_column(String, nullable=True)
    pula_id: Mapped[str] = mapped_column(String, nullable=True)
    language_spoken: Mapped[str] = mapped_column(String, nullable=True)
    birth_date_ec: Mapped[str] = mapped_column(String, nullable=True)
    estimated_age: Mapped[int] = mapped_column(Integer, nullable=True)
    marital_status: Mapped[str] = mapped_column(String, nullable=True)
    education_level: Mapped[str] = mapped_column(String, nullable=True)
    disabled: Mapped[bool] = mapped_column(Boolean, nullable=True)
    disability_type: Mapped[str] = mapped_column(String, nullable=True)
    disability_severity: Mapped[str] = mapped_column(String, nullable=True)
    source_of_income: Mapped[str] = mapped_column(String, nullable=True)
    source_of_income_other: Mapped[str] = mapped_column(String, nullable=True)
    is_psnp_user: Mapped[bool] = mapped_column(Boolean, nullable=True)
    is_farmer: Mapped[bool] = mapped_column(Boolean, nullable=True)
    farming_type: Mapped[str] = mapped_column(String, nullable=True)
    # Every phone number: [{phone_type, phone_number, country_code, is_primary,
    # phone_e164}]; mobile_number stays the primary one.
    phones: Mapped[list] = mapped_column(JSON, nullable=True)
    # SHA-256 of the photo held in record_image_document_id, so an unchanged
    # photo is not stored again.
    photo_sha256: Mapped[str] = mapped_column(String, nullable=True)


# All Register classes should have the prefix G2PRegister
class G2PRegisterFarmer(G2PRegister, G2PGeo, G2PFarmer):
    __tablename__ = "g2p_register_farmers"

    def get_search_text_fields(self) -> str:
        """Return farmer fields used to build search_text."""
        return G2PRegisterDomainServiceFarmer().construct_search_text(self.to_dict())

    def get_record_name_fields(self) -> str:
        """Return farmer record_name from domain service implementation."""
        return G2PRegisterDomainServiceFarmer().construct_record_name(self.to_dict())


# All Register History classes should have the prefix G2PRegisterHistory
class G2PRegisterHistoryFarmer(G2PRegisterHistory, G2PGeoHistory, G2PFarmer):
    __tablename__ = "g2p_register_history_farmers"


# All Intake Form classes should have the prefix G2PIntakeForm
class G2PIntakeFormFarmer(G2PIntakeForm, G2PRegister, G2PGeo, G2PFarmer):
    __tablename__ = "g2p_intake_form_farmers"

    def get_search_text_fields(self) -> str:
        """Return farmer fields used to build search_text."""
        return G2PRegisterDomainServiceFarmer().construct_search_text(self.to_dict())

    def get_record_name_fields(self) -> str:
        """Return farmer record_name from domain service implementation."""
        return G2PRegisterDomainServiceFarmer().construct_record_name(self.to_dict())
