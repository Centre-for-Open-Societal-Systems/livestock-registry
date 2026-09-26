"""ADMIN AREA — the Ethiopian administrative hierarchy, as collected in the field.

The platform's G2PGeo mixin models location generically (lat/long, two free-text
address lines, postal code, country). That is not how a livestock record is
located here: a holding is identified by where it sits in the
Region -> Zone -> Woreda -> Kebele ladder, which is what the surveyor records and
what every downstream report aggregates by.

These are plain String columns rather than references into the master-data geo
tree on purpose. The registry must accept a record from a surveyor working
offline in a woreda whose kebele has not been catalogued yet; a foreign key
would reject it. `geo_lowest_level_value_id` on G2PGeo remains available for the
resolved reference once master-data catches up.

Mixed into the farmer and livestock registers, so the register, history and
intake-form tables of both pick the columns up.
"""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column


class G2PAdminArea:
    """Region -> Zone -> Woreda -> Kebele, most general first."""

    region: Mapped[str] = mapped_column(String, nullable=True)
    zone: Mapped[str] = mapped_column(String, nullable=True)
    woreda: Mapped[str] = mapped_column(String, nullable=True)
    kebele: Mapped[str] = mapped_column(String, nullable=True)
