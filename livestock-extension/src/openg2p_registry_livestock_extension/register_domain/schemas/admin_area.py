"""Schema fields of the admin area columns (models/admin_area.py)."""

from typing import Optional


class G2PSchemaAdminArea:
    """Region -> Zone -> Woreda -> Kebele names and their Master Data ids."""

    region: Optional[str] = None
    zone: Optional[str] = None
    woreda: Optional[str] = None
    kebele: Optional[str] = None
    region_id: Optional[str] = None
    zone_id: Optional[str] = None
    woreda_id: Optional[str] = None
    kebele_id: Optional[str] = None
