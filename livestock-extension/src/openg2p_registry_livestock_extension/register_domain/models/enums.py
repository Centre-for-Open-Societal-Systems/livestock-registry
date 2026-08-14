"""Enumerations for values the livestock registry does NOT model as lookup tables.

Anything an administrator should be able to extend without a code change — species,
breed, vaccine, disease, approval status — is an **attribute lookup** instead: a plain
String column resolved against g2p_attributes / g2p_attribute_values and fed by the
master-data catalogue. What remains here are the closed value sets, taken verbatim from
the `fields.Selection` definitions in g2p_livestock_registry.
"""

from enum import StrEnum


class LivestockStateEnum(StrEnum):
    """Kebele -> Woreda -> Zone -> Region approval ladder (livestock_registry.py)."""

    DRAFT = "DRAFT"
    KEBELE_APPROVED = "KEBELE_APPROVED"
    WOREDA_APPROVED = "WOREDA_APPROVED"
    ZONE_APPROVED = "ZONE_APPROVED"
    VERIFIED = "VERIFIED"
    ARCHIVED = "ARCHIVED"


class SourceSystemEnum(StrEnum):
    MANUAL = "MANUAL"
    DOVAR = "DOVAR"
    LITS = "LITS"
    CASEBOOK = "CASEBOOK"
    ALIVE = "ALIVE"
    OFFLINE = "OFFLINE"


class SyncStatusEnum(StrEnum):
    SYNCED = "SYNCED"
    PENDING = "PENDING"
    CONFLICT = "CONFLICT"
    FAILED = "FAILED"


class AnimalStateEnum(StrEnum):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    DONE = "DONE"


class GenderEnum(StrEnum):
    MALE = "MALE"
    FEMALE = "FEMALE"


class HealthStatusEnum(StrEnum):
    HEALTHY = "HEALTHY"
    SICK = "SICK"
    QUARANTINED = "QUARANTINED"
    DECEASED = "DECEASED"


class VaccinationStatusEnum(StrEnum):
    UP_TO_DATE = "UP_TO_DATE"
    OVERDUE = "OVERDUE"
    NONE = "NONE"


class HealthEventTypeEnum(StrEnum):
    DISEASE = "DISEASE"
    INJURY = "INJURY"
    TREATMENT = "TREATMENT"
    RECOVERY = "RECOVERY"


class VitalEventTypeEnum(StrEnum):
    BIRTH = "BIRTH"
    MORTALITY = "MORTALITY"
    DISEASE = "DISEASE"


class VitalEventCauseEnum(StrEnum):
    DISEASE = "DISEASE"
    ACCIDENT = "ACCIDENT"
    PREDATION = "PREDATION"
    SLAUGHTER = "SLAUGHTER"
    UNKNOWN = "UNKNOWN"


class BreedingEventTypeEnum(StrEnum):
    NATURAL = "NATURAL"
    AI = "AI"


class BreedingOutcomeEnum(StrEnum):
    PENDING = "PENDING"
    SUCCESSFUL = "SUCCESSFUL"
    FAILED = "FAILED"


class EventLocationEnum(StrEnum):
    """Shared LOCATION_SELECTION in livestock_event.py."""

    HOME = "HOME"
    VETERINARY = "VETERINARY"
    MARKET = "MARKET"
    FIELD = "FIELD"
    QUARANTINE_CENTER = "QUARANTINE_CENTER"
    OTHER = "OTHER"


class ImportSourceSystemEnum(StrEnum):
    DOVAR = "DOVAR"
    LITS = "LITS"
    CASE_BOOK = "CASE_BOOK"
    ALIVE = "ALIVE"
    MANUAL = "MANUAL"


class ImportStateEnum(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AuditActionTypeEnum(StrEnum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    IMPORT = "IMPORT"
    SYNC = "SYNC"
