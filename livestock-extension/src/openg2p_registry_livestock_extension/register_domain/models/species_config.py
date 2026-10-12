"""Per-species configuration the livestock registry owns.

The code lists themselves (species, breed, vaccine, disease) live in Master
Data, which the platform reads over its API. Master Data knows a value's
code, label, parent and order and nothing else, so the two switches an
administrator sets per species — whether an animal of that species carries an
ear tag, and whether it is recorded as a flock with a head count — live in
this registry-side table, keyed by the Master Data value id.

The table keeps the name it had when the config hung off the platform's
attribute model (registry-platform 1.1), so an upgraded database keeps its rows.
"""

from openg2p_fastapi_common.models import BaseORMModel
from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column


class G2PLivestockSpeciesConfig(BaseORMModel):
    __tablename__ = "g2p_attribute_value_species_configs"
    __table_args__ = {"extend_existing": True}

    value_id: Mapped[str] = mapped_column(String, primary_key=True)
    requires_ear_tag: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_flock_species: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
