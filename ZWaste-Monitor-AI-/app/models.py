"""Persistent relational model layer for ZWaste Monitor AI.

Schema only: no queries, seeds, or UI here.

Identity is app-owned: ZWaste accounts are created with a first name,
surname, normalized unique email and an Argon2 password hash. A user
selects one of three self-registration roles (VIEWER, OPERATOR,
MUNICIPAL_ADMIN - shown as "Manager" in the UI); OPERATOR and
MUNICIPAL_ADMIN require an access code at registration time, VIEWER
never does. Registration access codes are recorded only as metadata
(which role gate was satisfied and when) - never the code value itself.

Security invariants enforced by this schema:
  * Passwords are stored ONLY as an Argon2 hash (`password_hash`).
  * Session tokens are stored ONLY as a hash (`session_token_hash`),
    alongside an expiry and last-login timestamp.
  * Failed login attempts and a temporary lockout timestamp support
    throttling; roles fail closed to VIEWER.
"""

from __future__ import annotations

import datetime
import enum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    MappedAsDataclass,
    mapped_column,
    relationship,
)


class Base(MappedAsDataclass, DeclarativeBase, kw_only=True):
    pass


# --------------------------------------------------------------------------
# Enums
# --------------------------------------------------------------------------


class UserRole(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    MUNICIPAL_ADMIN = "MUNICIPAL_ADMIN"
    OPERATOR = "OPERATOR"
    DRIVER = "DRIVER"
    ANALYST = "ANALYST"
    VIEWER = "VIEWER"


#: Fail-closed role for any account without an explicit grant.
DEFAULT_ROLE = UserRole.VIEWER

#: Roles a person may choose during self-registration.
SELF_REGISTRATION_ROLES: tuple[UserRole, ...] = (
    UserRole.VIEWER,
    UserRole.OPERATOR,
    UserRole.MUNICIPAL_ADMIN,
)

#: UI labels for the self-registration roles (MUNICIPAL_ADMIN = "Manager").
ROLE_LABELS: dict[UserRole, str] = {
    UserRole.SUPER_ADMIN: "Super admin",
    UserRole.MUNICIPAL_ADMIN: "Manager",
    UserRole.OPERATOR: "Operator",
    UserRole.DRIVER: "Driver",
    UserRole.ANALYST: "Analyst",
    UserRole.VIEWER: "Viewer",
}

#: Access codes required to self-register for a privileged role. VIEWER is
#: absent on purpose: viewers never see or enter a code. Consumed by the
#: later registration phase; never persisted on a user row.
ROLE_ACCESS_CODES: dict[UserRole, str] = {
    UserRole.OPERATOR: "2006",
    UserRole.MUNICIPAL_ADMIN: "6002",
}


class DataSource(str, enum.Enum):
    """Provenance label shown on every record surfaced in the UI."""

    SIMULATED = "SIMULATED"
    MANUAL = "MANUAL"
    SENSOR = "SENSOR"
    GATEZ_DEVICE = "GATEZ_DEVICE"
    API = "API"
    IMPORT = "IMPORT"
    DERIVED = "DERIVED"


class EntityKind(str, enum.Enum):
    INSTITUTION = "INSTITUTION"
    BUSINESS = "BUSINESS"
    HOSPITAL = "HOSPITAL"
    HOUSEHOLD = "HOUSEHOLD"
    PUBLIC_SPACE = "PUBLIC_SPACE"


class EntitySubtype(str, enum.Enum):
    """Normalized cluster subtype for a monitored Entity.

    Institution clusters use the four education subtypes; the Health
    Department cluster uses CLINIC/HOSPITAL_FACILITY. The remaining values
    keep every pre-existing EntityKind expressible so the column can be
    populated for business, household and public-space rows too.
    """

    # Institution cluster
    PRIMARY_SCHOOL = "PRIMARY_SCHOOL"
    SECONDARY_SCHOOL = "SECONDARY_SCHOOL"
    UNIVERSITY = "UNIVERSITY"
    COLLEGE = "COLLEGE"
    # Health Department cluster
    CLINIC = "CLINIC"
    HOSPITAL_FACILITY = "HOSPITAL_FACILITY"
    # Other existing entity kinds
    BUSINESS_PREMISES = "BUSINESS_PREMISES"
    HOUSEHOLD_UNIT = "HOUSEHOLD_UNIT"
    PUBLIC_SPACE_SITE = "PUBLIC_SPACE_SITE"
    OTHER = "OTHER"


#: Which subtypes belong to which cluster (EntityKind). Used by later
#: registration / administration phases to constrain the choices offered.
ENTITY_SUBTYPES_BY_KIND: dict[EntityKind, tuple[EntitySubtype, ...]] = {
    EntityKind.INSTITUTION: (
        EntitySubtype.PRIMARY_SCHOOL,
        EntitySubtype.SECONDARY_SCHOOL,
        EntitySubtype.UNIVERSITY,
        EntitySubtype.COLLEGE,
    ),
    EntityKind.HOSPITAL: (
        EntitySubtype.CLINIC,
        EntitySubtype.HOSPITAL_FACILITY,
    ),
    EntityKind.BUSINESS: (EntitySubtype.BUSINESS_PREMISES,),
    EntityKind.HOUSEHOLD: (EntitySubtype.HOUSEHOLD_UNIT,),
    EntityKind.PUBLIC_SPACE: (EntitySubtype.PUBLIC_SPACE_SITE,),
}

#: UI labels for the normalized subtypes.
ENTITY_SUBTYPE_LABELS: dict[EntitySubtype, str] = {
    EntitySubtype.PRIMARY_SCHOOL: "Primary School",
    EntitySubtype.SECONDARY_SCHOOL: "Secondary School",
    EntitySubtype.UNIVERSITY: "University",
    EntitySubtype.COLLEGE: "College",
    EntitySubtype.CLINIC: "Clinic",
    EntitySubtype.HOSPITAL_FACILITY: "Hospital",
    EntitySubtype.BUSINESS_PREMISES: "Business premises",
    EntitySubtype.HOUSEHOLD_UNIT: "Household",
    EntitySubtype.PUBLIC_SPACE_SITE: "Public space",
    EntitySubtype.OTHER: "Other",
}


class PlaceProvenance(str, enum.Enum):
    """Where an Entity's place identity came from."""

    MANUAL = "MANUAL"
    GOOGLE_PLACES = "GOOGLE_PLACES"
    SEEDED = "SEEDED"


class CollectionStatus(str, enum.Enum):
    """Manually recorded collection outcome for a waste measurement."""

    NOT_COLLECTED = "NOT_COLLECTED"
    COLLECTED = "COLLECTED"


class TelemetryStatus(str, enum.Enum):
    """Normalized live-tracking status (provider-neutral vocabulary)."""

    UNKNOWN = "UNKNOWN"
    MOVING = "MOVING"
    IDLE = "IDLE"
    OFFLINE = "OFFLINE"
    STALE = "STALE"


class TelemetrySource(str, enum.Enum):
    """Origin of a persisted vehicle position."""

    NONE = "NONE"
    SIMULATED = "SIMULATED"
    BROWSER_GPS = "BROWSER_GPS"
    TRACKER_API = "TRACKER_API"
    MANUAL = "MANUAL"


class BinStatus(str, enum.Enum):
    OK = "OK"
    FILLING = "FILLING"
    NEAR_FULL = "NEAR_FULL"
    FULL = "FULL"
    OVERFLOW = "OVERFLOW"
    OFFLINE = "OFFLINE"
    MAINTENANCE = "MAINTENANCE"


class SensorStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    FAULTY = "FAULTY"
    LOW_BATTERY = "LOW_BATTERY"
    CALIBRATING = "CALIBRATING"


class VehicleStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    ON_ROUTE = "ON_ROUTE"
    MAINTENANCE = "MAINTENANCE"
    OUT_OF_SERVICE = "OUT_OF_SERVICE"


class RouteStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class StopStatus(str, enum.Enum):
    PENDING = "PENDING"
    EN_ROUTE = "EN_ROUTE"
    COLLECTED = "COLLECTED"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"


class AlertSeverity(str, enum.Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertKind(str, enum.Enum):
    BIN_FULL = "BIN_FULL"
    OVERFLOW_FORECAST = "OVERFLOW_FORECAST"
    SENSOR_FAULT = "SENSOR_FAULT"
    SENSOR_OFFLINE = "SENSOR_OFFLINE"
    ANOMALY = "ANOMALY"
    ROUTE_DELAY = "ROUTE_DELAY"
    MISSED_COLLECTION = "MISSED_COLLECTION"
    HAZARDOUS_WASTE = "HAZARDOUS_WASTE"


class AlertStatus(str, enum.Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class PredictionKind(str, enum.Enum):
    OVERFLOW_FORECAST = "OVERFLOW_FORECAST"
    VOLUME_FORECAST = "VOLUME_FORECAST"
    ANOMALY_SCORE = "ANOMALY_SCORE"
    COLLECTION_RECOMMENDATION = "COLLECTION_RECOMMENDATION"
    ROUTE_RECOMMENDATION = "ROUTE_RECOMMENDATION"
    VEHICLE_RECOMMENDATION = "VEHICLE_RECOMMENDATION"


class ApprovalStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class ReportKind(str, enum.Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    ENTITY = "ENTITY"
    AREA = "AREA"
    WASTE_TYPE = "WASTE_TYPE"
    PERFORMANCE = "PERFORMANCE"
    CUSTOM = "CUSTOM"


class ReportFormat(str, enum.Enum):
    CSV = "CSV"
    PDF = "PDF"


class ReportStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    GENERATING = "GENERATING"
    READY = "READY"
    FAILED = "FAILED"


class AuditAction(str, enum.Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DEACTIVATE = "DEACTIVATE"
    REACTIVATE = "REACTIVATE"
    DELETE = "DELETE"
    LOGIN = "LOGIN"
    ROLE_CHANGE = "ROLE_CHANGE"
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    EXPORT = "EXPORT"
    SIMULATE = "SIMULATE"


def _enum(py_enum: type[enum.Enum], name: str) -> Enum:
    return Enum(py_enum, name=name, native_enum=False, validate_strings=True)


# --------------------------------------------------------------------------
# Timestamp mixin
# --------------------------------------------------------------------------


class TimestampMixin(MappedAsDataclass):
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), init=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        init=False,
    )


# --------------------------------------------------------------------------
# Identity & tenancy
# --------------------------------------------------------------------------


class AppUser(TimestampMixin, Base):
    """App-owned account: email + Argon2 password hash, keyed on `id`.

    Primary key and every inbound foreign key (audit, report, route,
    waste record, driver, membership, prediction, alert) are unchanged, so
    existing operational history keeps resolving to the same user rows.
    """

    __tablename__ = "app_user"
    __table_args__ = (
        UniqueConstraint("email", name="uq_app_user_email"),
        Index("ix_app_user_role_active", "role", "is_active"),
        Index("ix_app_user_session_token_hash", "session_token_hash"),
        Index("ix_app_user_session_expires", "session_expires_at"),
        Index(
            "ix_app_user_muni_assigned_entity",
            "default_municipality_id",
            "assigned_entity_id",
        ),
        CheckConstraint(
            "failed_login_count >= 0", name="ck_app_user_failed_login_count"
        ),
        CheckConstraint("length(email) > 0", name="ck_app_user_email_present"),
        CheckConstraint(
            "length(first_name) > 0", name="ck_app_user_first_name_present"
        ),
        CheckConstraint(
            "length(surname) > 0", name="ck_app_user_surname_present"
        ),
        CheckConstraint(
            "length(password_hash) > 0", name="ck_app_user_password_hash"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    # NOTE: these four columns were added to an EMPTY `app_user` table. They
    # carry a temporary, non-secret empty-string server default purely so the
    # PostgreSQL autogenerated migration can add them as NOT NULL without a
    # backfill. Application code always supplies real values, and the
    # presence CheckConstraints above still reject empty strings.
    first_name: Mapped[str] = mapped_column(String(120), server_default="")
    surname: Mapped[str] = mapped_column(String(120), server_default="")
    #: Lower-cased, trimmed email; the account's unique login identifier.
    email: Mapped[str] = mapped_column(String(320), server_default="")
    #: Argon2 hash (argon2-cffi PHC string). NEVER a plaintext password.
    password_hash: Mapped[str] = mapped_column(Text, server_default="")
    password_changed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    display_name: Mapped[str | None] = mapped_column(String(255), default=None)
    picture_url: Mapped[str | None] = mapped_column(Text, default=None)
    locale: Mapped[str | None] = mapped_column(String(32), default=None)
    #: One of SELF_REGISTRATION_ROLES for self-registered accounts; other
    #: roles are granted administratively. Fails closed to VIEWER.
    role: Mapped[UserRole] = mapped_column(
        _enum(UserRole, "user_role"), default=DEFAULT_ROLE
    )
    #: Role the access code unlocked at registration (metadata only - the
    #: code value itself is never stored).
    role_code_verified_for: Mapped[UserRole | None] = mapped_column(
        _enum(UserRole, "user_role"), default=None
    )
    role_code_verified_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    #: Terms of service / privacy policy acceptance.
    terms_accepted_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    privacy_accepted_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    #: Hash of the active session token. NEVER the token itself.
    session_token_hash: Mapped[str | None] = mapped_column(
        String(128), default=None
    )
    session_issued_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    session_expires_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0)
    #: Temporary lockout: logins are refused until this moment passes.
    locked_until: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    last_failed_login_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    #: Required municipality selection at registration is enforced by the
    #: application (and mirrored by a MunicipalityMembership row); the column
    #: stays nullable so existing rows and SET NULL deletes remain valid.
    default_municipality_id: Mapped[int | None] = mapped_column(
        ForeignKey("municipality.id", ondelete="SET NULL"), default=None
    )
    #: Cluster (Entity) this account is assigned to. Operators may later
    #: record collections only for their own municipality and this cluster;
    #: Managers edit clusters/bins; Viewers stay read-only.
    assigned_entity_id: Mapped[int | None] = mapped_column(
        ForeignKey("entity.id", ondelete="SET NULL"), default=None
    )
    assigned_entity_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )

    memberships: Mapped[list["MunicipalityMembership"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        default_factory=list,
        foreign_keys="MunicipalityMembership.user_id",
    )


class Municipality(TimestampMixin, Base):
    """Tenant root: every operational record hangs off a municipality."""

    __tablename__ = "municipality"
    __table_args__ = (
        UniqueConstraint("code", name="uq_municipality_code"),
        Index("ix_municipality_active_name", "is_active", "name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    name: Mapped[str] = mapped_column(String(160))
    code: Mapped[str] = mapped_column(String(32))
    region: Mapped[str | None] = mapped_column(String(120), default=None)
    country: Mapped[str | None] = mapped_column(String(120), default=None)
    population: Mapped[int | None] = mapped_column(Integer, default=None)
    area_km2: Mapped[float | None] = mapped_column(Float, default=None)
    contact_email: Mapped[str | None] = mapped_column(String(320), default=None)
    contact_phone: Mapped[str | None] = mapped_column(String(64), default=None)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    latitude: Mapped[float | None] = mapped_column(Float, default=None)
    longitude: Mapped[float | None] = mapped_column(Float, default=None)
    performance_score: Mapped[float | None] = mapped_column(Float, default=None)
    source: Mapped[DataSource] = mapped_column(
        _enum(DataSource, "data_source"), default=DataSource.SIMULATED
    )
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    entities: Mapped[list["Entity"]] = relationship(
        back_populates="municipality",
        cascade="all, delete-orphan",
        default_factory=list,
    )
    waste_types: Mapped[list["WasteType"]] = relationship(
        back_populates="municipality",
        cascade="all, delete-orphan",
        default_factory=list,
    )


class MunicipalityMembership(TimestampMixin, Base):
    """Scopes a user's role to a municipality (isolation boundary)."""

    __tablename__ = "municipality_membership"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "municipality_id", name="uq_membership_user_muni"
        ),
        Index("ix_membership_municipality_role", "municipality_id", "role"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), index=True
    )
    municipality_id: Mapped[int] = mapped_column(
        ForeignKey("municipality.id", ondelete="CASCADE")
    )
    role: Mapped[UserRole] = mapped_column(
        _enum(UserRole, "user_role"), default=DEFAULT_ROLE
    )
    granted_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL"), default=None
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped["AppUser"] = relationship(
        back_populates="memberships", foreign_keys=[user_id], default=None
    )


# --------------------------------------------------------------------------
# Monitored entities
# --------------------------------------------------------------------------


class Entity(TimestampMixin, Base):
    """Common record for institutions, businesses, hospitals, households.

    Kind-specific attributes live in the one-to-one profile tables below.
    """

    __tablename__ = "entity"
    __table_args__ = (
        UniqueConstraint("municipality_id", "code", name="uq_entity_muni_code"),
        Index(
            "ix_entity_muni_kind_active", "municipality_id", "kind", "is_active"
        ),
        Index("ix_entity_name", "name"),
        Index("ix_entity_muni_subtype", "municipality_id", "subtype"),
        #: Per-municipality uniqueness for Google place IDs: the same place
        #: may not be saved twice inside one municipality, while different
        #: municipalities remain independent and NULLs stay unconstrained.
        UniqueConstraint(
            "municipality_id", "google_place_id", name="uq_entity_muni_place_id"
        ),
        CheckConstraint(
            "google_place_id IS NULL OR length(google_place_id) > 0",
            name="ck_entity_google_place_id_present",
        ),
        CheckConstraint(
            "latitude IS NULL OR (latitude >= -90 AND latitude <= 90)",
            name="ck_entity_latitude_range",
        ),
        CheckConstraint(
            "longitude IS NULL OR (longitude >= -180 AND longitude <= 180)",
            name="ck_entity_longitude_range",
        ),
        CheckConstraint(
            "expected_daily_kg IS NULL OR expected_daily_kg >= 0",
            name="ck_entity_expected_daily_kg",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    municipality_id: Mapped[int] = mapped_column(
        ForeignKey("municipality.id", ondelete="CASCADE")
    )
    kind: Mapped[EntityKind] = mapped_column(_enum(EntityKind, "entity_kind"))
    name: Mapped[str] = mapped_column(String(200))
    #: Normalized cluster subtype (see ENTITY_SUBTYPES_BY_KIND). Nullable so
    #: existing rows migrate without a backfill.
    subtype: Mapped[EntitySubtype | None] = mapped_column(
        _enum(EntitySubtype, "entity_subtype"), default=None
    )
    #: Google Places place ID, unique per municipality when present.
    google_place_id: Mapped[str | None] = mapped_column(
        String(255), default=None
    )
    google_place_name: Mapped[str | None] = mapped_column(
        String(255), default=None
    )
    google_place_address: Mapped[str | None] = mapped_column(Text, default=None)
    google_place_saved_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    #: use_alter: entity -> app_user and app_user.assigned_entity_id ->
    #: entity form a legitimate FK cycle; emitting this one as a separate
    #: ALTER keeps table sorting acyclic.
    google_place_saved_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "app_user.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_entity_google_place_saved_by_user",
        ),
        default=None,
    )
    #: Provenance of the place identity above. Migration-safe server default.
    place_provenance: Mapped[PlaceProvenance] = mapped_column(
        _enum(PlaceProvenance, "place_provenance"),
        server_default=PlaceProvenance.MANUAL.value,
        default=PlaceProvenance.MANUAL,
    )
    code: Mapped[str | None] = mapped_column(String(48), default=None)
    area_name: Mapped[str | None] = mapped_column(String(120), default=None)
    address: Mapped[str | None] = mapped_column(Text, default=None)
    latitude: Mapped[float | None] = mapped_column(Float, default=None)
    longitude: Mapped[float | None] = mapped_column(Float, default=None)
    contact_name: Mapped[str | None] = mapped_column(String(160), default=None)
    contact_email: Mapped[str | None] = mapped_column(String(320), default=None)
    contact_phone: Mapped[str | None] = mapped_column(String(64), default=None)
    occupancy: Mapped[int | None] = mapped_column(Integer, default=None)
    expected_daily_kg: Mapped[float | None] = mapped_column(Float, default=None)
    source: Mapped[DataSource] = mapped_column(
        _enum(DataSource, "data_source"), default=DataSource.SIMULATED
    )
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    #: Households are architecture-only for now and stay inactive.
    is_future_architecture: Mapped[bool] = mapped_column(Boolean, default=False)

    municipality: Mapped["Municipality"] = relationship(
        back_populates="entities", default=None
    )
    bins: Mapped[list["Bin"]] = relationship(
        back_populates="entity",
        cascade="all, delete-orphan",
        default_factory=list,
    )


class InstitutionProfile(TimestampMixin, Base):
    __tablename__ = "institution_profile"

    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entity.id", ondelete="CASCADE"), primary_key=True
    )
    institution_type: Mapped[str | None] = mapped_column(
        String(120), default=None
    )
    student_count: Mapped[int | None] = mapped_column(Integer, default=None)
    staff_count: Mapped[int | None] = mapped_column(Integer, default=None)
    campus_count: Mapped[int] = mapped_column(Integer, default=1)
    recycling_program: Mapped[bool] = mapped_column(Boolean, default=False)


class BusinessProfile(TimestampMixin, Base):
    __tablename__ = "business_profile"

    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entity.id", ondelete="CASCADE"), primary_key=True
    )
    sector: Mapped[str | None] = mapped_column(String(120), default=None)
    registration_number: Mapped[str | None] = mapped_column(
        String(64), default=None
    )
    employee_count: Mapped[int | None] = mapped_column(Integer, default=None)
    operating_hours: Mapped[str | None] = mapped_column(
        String(120), default=None
    )
    commercial_waste_licence: Mapped[str | None] = mapped_column(
        String(64), default=None
    )


class HospitalProfile(TimestampMixin, Base):
    __tablename__ = "hospital_profile"

    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entity.id", ondelete="CASCADE"), primary_key=True
    )
    facility_level: Mapped[str | None] = mapped_column(
        String(120), default=None
    )
    bed_count: Mapped[int | None] = mapped_column(Integer, default=None)
    has_incinerator: Mapped[bool] = mapped_column(Boolean, default=False)
    hazardous_handling_certified: Mapped[bool] = mapped_column(
        Boolean, default=False
    )
    biohazard_pickup_frequency_per_week: Mapped[int | None] = mapped_column(
        Integer, default=None
    )


class HouseholdProfile(TimestampMixin, Base):
    """Inactive future-household architecture (not surfaced in the UI yet)."""

    __tablename__ = "household_profile"

    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entity.id", ondelete="CASCADE"), primary_key=True
    )
    dwelling_type: Mapped[str | None] = mapped_column(String(120), default=None)
    resident_count: Mapped[int | None] = mapped_column(Integer, default=None)
    household_head: Mapped[str | None] = mapped_column(
        String(160), default=None
    )
    subscription_plan: Mapped[str | None] = mapped_column(
        String(64), default=None
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)


# --------------------------------------------------------------------------
# Waste taxonomy, bins & sensors
# --------------------------------------------------------------------------


class WasteType(TimestampMixin, Base):
    __tablename__ = "waste_type"
    __table_args__ = (
        UniqueConstraint(
            "municipality_id", "code", name="uq_waste_type_muni_code"
        ),
        Index("ix_waste_type_muni_active", "municipality_id", "is_active"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    municipality_id: Mapped[int] = mapped_column(
        ForeignKey("municipality.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(120))
    code: Mapped[str] = mapped_column(String(32))
    category: Mapped[str | None] = mapped_column(String(80), default=None)
    color_hex: Mapped[str] = mapped_column(String(9), default="#A3E635")
    is_hazardous: Mapped[bool] = mapped_column(Boolean, default=False)
    is_recyclable: Mapped[bool] = mapped_column(Boolean, default=False)
    density_kg_per_m3: Mapped[float | None] = mapped_column(Float, default=None)
    handling_instructions: Mapped[str | None] = mapped_column(
        Text, default=None
    )
    disposal_cost_per_kg: Mapped[float | None] = mapped_column(
        Float, default=None
    )
    source: Mapped[DataSource] = mapped_column(
        _enum(DataSource, "data_source"), default=DataSource.SIMULATED
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    municipality: Mapped["Municipality"] = relationship(
        back_populates="waste_types", default=None
    )


class Bin(TimestampMixin, Base):
    __tablename__ = "bin"
    __table_args__ = (
        UniqueConstraint("municipality_id", "code", name="uq_bin_muni_code"),
        Index("ix_bin_muni_status", "municipality_id", "status"),
        Index("ix_bin_entity", "entity_id"),
        CheckConstraint(
            "fill_percent >= 0 AND fill_percent <= 100",
            name="ck_bin_fill_range",
        ),
        CheckConstraint(
            "latitude IS NULL OR (latitude >= -90 AND latitude <= 90)",
            name="ck_bin_latitude_range",
        ),
        CheckConstraint(
            "longitude IS NULL OR (longitude >= -180 AND longitude <= 180)",
            name="ck_bin_longitude_range",
        ),
        CheckConstraint(
            "capacity_liters >= 0", name="ck_bin_capacity_liters_nonneg"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    municipality_id: Mapped[int] = mapped_column(
        ForeignKey("municipality.id", ondelete="CASCADE")
    )
    entity_id: Mapped[int | None] = mapped_column(
        ForeignKey("entity.id", ondelete="SET NULL"), default=None
    )
    waste_type_id: Mapped[int | None] = mapped_column(
        ForeignKey("waste_type.id", ondelete="SET NULL"), default=None
    )
    code: Mapped[str] = mapped_column(String(48), default="")
    label: Mapped[str | None] = mapped_column(String(160), default=None)
    container_type: Mapped[str | None] = mapped_column(String(80), default=None)
    capacity_liters: Mapped[float] = mapped_column(Float, default=240.0)
    capacity_kg: Mapped[float | None] = mapped_column(Float, default=None)
    fill_percent: Mapped[float] = mapped_column(Float, default=0.0)
    current_weight_kg: Mapped[float | None] = mapped_column(Float, default=None)
    status: Mapped[BinStatus] = mapped_column(
        _enum(BinStatus, "bin_status"), default=BinStatus.OK
    )
    latitude: Mapped[float | None] = mapped_column(Float, default=None)
    longitude: Mapped[float | None] = mapped_column(Float, default=None)
    area_name: Mapped[str | None] = mapped_column(String(120), default=None)
    installed_on: Mapped[datetime.date | None] = mapped_column(default=None)
    last_reading_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    last_emptied_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    full_threshold_percent: Mapped[float] = mapped_column(Float, default=85.0)
    source: Mapped[DataSource] = mapped_column(
        _enum(DataSource, "data_source"), default=DataSource.SIMULATED
    )
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    entity: Mapped["Entity | None"] = relationship(
        back_populates="bins", default=None
    )
    sensors: Mapped[list["Sensor"]] = relationship(
        back_populates="bin", cascade="all, delete-orphan", default_factory=list
    )


class Sensor(TimestampMixin, Base):
    __tablename__ = "sensor"
    __table_args__ = (
        UniqueConstraint("device_serial", name="uq_sensor_device_serial"),
        Index("ix_sensor_muni_status", "municipality_id", "status"),
        Index("ix_sensor_bin", "bin_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    municipality_id: Mapped[int] = mapped_column(
        ForeignKey("municipality.id", ondelete="CASCADE")
    )
    bin_id: Mapped[int | None] = mapped_column(
        ForeignKey("bin.id", ondelete="SET NULL"), default=None
    )
    device_serial: Mapped[str] = mapped_column(String(64), default="")
    model: Mapped[str] = mapped_column(String(80), default="GateZ-1")
    firmware_version: Mapped[str | None] = mapped_column(
        String(48), default=None
    )
    status: Mapped[SensorStatus] = mapped_column(
        _enum(SensorStatus, "sensor_status"), default=SensorStatus.ACTIVE
    )
    battery_percent: Mapped[float | None] = mapped_column(Float, default=None)
    signal_strength_dbm: Mapped[float | None] = mapped_column(
        Float, default=None
    )
    reporting_interval_minutes: Mapped[int] = mapped_column(Integer, default=30)
    installed_on: Mapped[datetime.date | None] = mapped_column(default=None)
    last_seen_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    last_calibrated_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    source: Mapped[DataSource] = mapped_column(
        _enum(DataSource, "data_source"), default=DataSource.SIMULATED
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    bin: Mapped["Bin | None"] = relationship(
        back_populates="sensors", default=None
    )
    readings: Mapped[list["SensorReading"]] = relationship(
        back_populates="sensor",
        cascade="all, delete-orphan",
        default_factory=list,
    )


class SensorReading(Base):
    """Append-only sensor history (also the GateZ simulator's landing table)."""

    __tablename__ = "sensor_reading"
    __table_args__ = (
        Index("ix_reading_sensor_time", "sensor_id", "recorded_at"),
        Index("ix_reading_bin_time", "bin_id", "recorded_at"),
        Index("ix_reading_muni_time", "municipality_id", "recorded_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    municipality_id: Mapped[int] = mapped_column(
        ForeignKey("municipality.id", ondelete="CASCADE")
    )
    sensor_id: Mapped[int] = mapped_column(
        ForeignKey("sensor.id", ondelete="CASCADE")
    )
    bin_id: Mapped[int | None] = mapped_column(
        ForeignKey("bin.id", ondelete="SET NULL"), default=None
    )
    recorded_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=None
    )
    fill_percent: Mapped[float | None] = mapped_column(Float, default=None)
    weight_kg: Mapped[float | None] = mapped_column(Float, default=None)
    distance_cm: Mapped[float | None] = mapped_column(Float, default=None)
    temperature_c: Mapped[float | None] = mapped_column(Float, default=None)
    humidity_percent: Mapped[float | None] = mapped_column(Float, default=None)
    gas_ppm: Mapped[float | None] = mapped_column(Float, default=None)
    battery_percent: Mapped[float | None] = mapped_column(Float, default=None)
    lid_open: Mapped[bool | None] = mapped_column(Boolean, default=None)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True)
    validation_error: Mapped[str | None] = mapped_column(Text, default=None)
    raw_payload: Mapped[str | None] = mapped_column(Text, default=None)
    source: Mapped[DataSource] = mapped_column(
        _enum(DataSource, "data_source"), default=DataSource.GATEZ_DEVICE
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), init=False
    )


class WasteRecord(TimestampMixin, Base):
    """A measured/collected quantity of waste attributed to an entity."""

    __tablename__ = "waste_record"
    __table_args__ = (
        Index("ix_waste_record_muni_time", "municipality_id", "collected_at"),
        Index("ix_waste_record_entity_time", "entity_id", "collected_at"),
        Index("ix_waste_record_type", "waste_type_id"),
        Index(
            "ix_waste_record_muni_status_date",
            "municipality_id",
            "collection_status",
            "measured_on",
        ),
        CheckConstraint("quantity_kg >= 0", name="ck_waste_record_qty"),
        CheckConstraint(
            "volume_liters IS NULL OR volume_liters >= 0",
            name="ck_waste_record_volume",
        ),
        CheckConstraint(
            "recycled_kg IS NULL OR recycled_kg >= 0",
            name="ck_waste_record_recycled",
        ),
        CheckConstraint(
            "landfill_kg IS NULL OR landfill_kg >= 0",
            name="ck_waste_record_landfill",
        ),
        #: Valid collection semantics: a record is only a collection when it
        #: is explicitly marked COLLECTED, and then it must carry the date it
        #: was collected on. NOT_COLLECTED records must not carry one.
        CheckConstraint(
            "(collection_status = 'COLLECTED' AND collected_on IS NOT NULL)"
            " OR (collection_status <> 'COLLECTED' AND collected_on IS NULL)",
            name="ck_waste_record_collection_semantics",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    municipality_id: Mapped[int] = mapped_column(
        ForeignKey("municipality.id", ondelete="CASCADE")
    )
    entity_id: Mapped[int | None] = mapped_column(
        ForeignKey("entity.id", ondelete="SET NULL"), default=None
    )
    bin_id: Mapped[int | None] = mapped_column(
        ForeignKey("bin.id", ondelete="SET NULL"), default=None
    )
    waste_type_id: Mapped[int | None] = mapped_column(
        ForeignKey("waste_type.id", ondelete="SET NULL"), default=None
    )
    route_stop_id: Mapped[int | None] = mapped_column(
        ForeignKey("route_stop.id", ondelete="SET NULL"), default=None
    )
    driver_id: Mapped[int | None] = mapped_column(
        ForeignKey("driver.id", ondelete="SET NULL"), default=None
    )
    vehicle_id: Mapped[int | None] = mapped_column(
        ForeignKey("vehicle.id", ondelete="SET NULL"), default=None
    )
    #: Timestamp the row was written/observed. Preserved as-is: it is NOT
    #: evidence that a collection happened - see `collection_status`.
    collected_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=None
    )
    #: Explicit manual collection model. Existing rows default to
    #: NOT_COLLECTED (with a NULL `collected_on`) so no historical
    #: measurement is retroactively treated as a collection.
    collection_status: Mapped[CollectionStatus] = mapped_column(
        _enum(CollectionStatus, "collection_status"),
        server_default=CollectionStatus.NOT_COLLECTED.value,
        default=CollectionStatus.NOT_COLLECTED,
    )
    #: Date the operator says the waste was actually collected. Required
    #: when (and only when) collection_status is COLLECTED.
    collected_on: Mapped[datetime.date | None] = mapped_column(default=None)
    #: Date the amount was measured, independent of any collection.
    measured_on: Mapped[datetime.date | None] = mapped_column(default=None)
    collection_status_set_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    collection_status_set_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL"), default=None
    )
    #: True when an Operator entered this record by hand.
    is_manual_entry: Mapped[bool] = mapped_column(
        Boolean, server_default="false", default=False
    )
    quantity_kg: Mapped[float] = mapped_column(Float, default=0.0)
    volume_liters: Mapped[float | None] = mapped_column(Float, default=None)
    recycled_kg: Mapped[float | None] = mapped_column(Float, default=None)
    landfill_kg: Mapped[float | None] = mapped_column(Float, default=None)
    disposal_site: Mapped[str | None] = mapped_column(String(160), default=None)
    cost: Mapped[float | None] = mapped_column(Float, default=None)
    recorded_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL"), default=None
    )
    source: Mapped[DataSource] = mapped_column(
        _enum(DataSource, "data_source"), default=DataSource.SIMULATED
    )
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# --------------------------------------------------------------------------
# Fleet & field operations
# --------------------------------------------------------------------------


class Driver(TimestampMixin, Base):
    __tablename__ = "driver"
    __table_args__ = (
        UniqueConstraint(
            "municipality_id", "employee_code", name="uq_driver_muni_code"
        ),
        Index("ix_driver_muni_active", "municipality_id", "is_active"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    municipality_id: Mapped[int] = mapped_column(
        ForeignKey("municipality.id", ondelete="CASCADE")
    )
    full_name: Mapped[str] = mapped_column(String(180))
    employee_code: Mapped[str] = mapped_column(String(48), default="")
    phone: Mapped[str | None] = mapped_column(String(64), default=None)
    email: Mapped[str | None] = mapped_column(String(320), default=None)
    licence_number: Mapped[str | None] = mapped_column(String(64), default=None)
    licence_class: Mapped[str | None] = mapped_column(String(32), default=None)
    licence_expires_on: Mapped[datetime.date | None] = mapped_column(
        default=None
    )
    shift: Mapped[str | None] = mapped_column(String(48), default=None)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL"), default=None
    )
    source: Mapped[DataSource] = mapped_column(
        _enum(DataSource, "data_source"), default=DataSource.SIMULATED
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Vehicle(TimestampMixin, Base):
    __tablename__ = "vehicle"
    __table_args__ = (
        UniqueConstraint(
            "municipality_id", "plate_number", name="uq_vehicle_muni_plate"
        ),
        Index("ix_vehicle_muni_status", "municipality_id", "status"),
        Index(
            "ix_vehicle_muni_position_time",
            "municipality_id",
            "last_position_at",
        ),
        CheckConstraint(
            "last_latitude IS NULL"
            " OR (last_latitude >= -90 AND last_latitude <= 90)",
            name="ck_vehicle_last_latitude_range",
        ),
        CheckConstraint(
            "last_longitude IS NULL"
            " OR (last_longitude >= -180 AND last_longitude <= 180)",
            name="ck_vehicle_last_longitude_range",
        ),
        CheckConstraint(
            "last_speed_kmh IS NULL OR last_speed_kmh >= 0",
            name="ck_vehicle_last_speed_nonneg",
        ),
        CheckConstraint(
            "last_heading_degrees IS NULL OR"
            " (last_heading_degrees >= 0 AND last_heading_degrees <= 360)",
            name="ck_vehicle_last_heading_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    municipality_id: Mapped[int] = mapped_column(
        ForeignKey("municipality.id", ondelete="CASCADE")
    )
    plate_number: Mapped[str] = mapped_column(String(32))
    label: Mapped[str | None] = mapped_column(String(120), default=None)
    make: Mapped[str | None] = mapped_column(String(80), default=None)
    model: Mapped[str | None] = mapped_column(String(80), default=None)
    year: Mapped[int | None] = mapped_column(Integer, default=None)
    capacity_kg: Mapped[float | None] = mapped_column(Float, default=None)
    capacity_liters: Mapped[float | None] = mapped_column(Float, default=None)
    fuel_type: Mapped[str | None] = mapped_column(String(48), default=None)
    odometer_km: Mapped[float | None] = mapped_column(Float, default=None)
    status: Mapped[VehicleStatus] = mapped_column(
        _enum(VehicleStatus, "vehicle_status"), default=VehicleStatus.AVAILABLE
    )
    last_latitude: Mapped[float | None] = mapped_column(Float, default=None)
    last_longitude: Mapped[float | None] = mapped_column(Float, default=None)
    last_position_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    #: Normalized latest telemetry (provider-neutral). Nullable / server
    #: defaulted so existing vehicle rows migrate untouched.
    last_speed_kmh: Mapped[float | None] = mapped_column(Float, default=None)
    last_heading_degrees: Mapped[float | None] = mapped_column(
        Float, default=None
    )
    telemetry_status: Mapped[TelemetryStatus] = mapped_column(
        _enum(TelemetryStatus, "telemetry_status"),
        server_default=TelemetryStatus.UNKNOWN.value,
        default=TelemetryStatus.UNKNOWN,
    )
    telemetry_source: Mapped[TelemetrySource] = mapped_column(
        _enum(TelemetrySource, "telemetry_source"),
        server_default=TelemetrySource.NONE.value,
        default=TelemetrySource.NONE,
    )
    #: External tracker identifier, when a provider is configured.
    tracker_device_id: Mapped[str | None] = mapped_column(
        String(128), default=None
    )
    telemetry_updated_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    next_service_due_on: Mapped[datetime.date | None] = mapped_column(
        default=None
    )
    source: Mapped[DataSource] = mapped_column(
        _enum(DataSource, "data_source"), default=DataSource.SIMULATED
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class VehicleLocation(Base):
    """Append-only vehicle position history (tracker API or browser GPS).

    Never updated in place: each poll or GPS sample appends one row, so the
    live map can show a trail and detect stale data by comparing
    `recorded_at` with now.
    """

    __tablename__ = "vehicle_location"
    __table_args__ = (
        Index(
            "ix_vehicle_location_muni_time", "municipality_id", "recorded_at"
        ),
        Index("ix_vehicle_location_vehicle_time", "vehicle_id", "recorded_at"),
        Index("ix_vehicle_location_time", "recorded_at"),
        CheckConstraint(
            "latitude >= -90 AND latitude <= 90",
            name="ck_vehicle_location_latitude_range",
        ),
        CheckConstraint(
            "longitude >= -180 AND longitude <= 180",
            name="ck_vehicle_location_longitude_range",
        ),
        CheckConstraint(
            "speed_kmh IS NULL OR speed_kmh >= 0",
            name="ck_vehicle_location_speed_nonneg",
        ),
        CheckConstraint(
            "heading_degrees IS NULL OR"
            " (heading_degrees >= 0 AND heading_degrees <= 360)",
            name="ck_vehicle_location_heading_range",
        ),
        CheckConstraint(
            "accuracy_meters IS NULL OR accuracy_meters >= 0",
            name="ck_vehicle_location_accuracy_nonneg",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    municipality_id: Mapped[int] = mapped_column(
        ForeignKey("municipality.id", ondelete="CASCADE")
    )
    vehicle_id: Mapped[int] = mapped_column(
        ForeignKey("vehicle.id", ondelete="CASCADE")
    )
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    recorded_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=None
    )
    speed_kmh: Mapped[float | None] = mapped_column(Float, default=None)
    heading_degrees: Mapped[float | None] = mapped_column(Float, default=None)
    accuracy_meters: Mapped[float | None] = mapped_column(Float, default=None)
    telemetry_status: Mapped[TelemetryStatus] = mapped_column(
        _enum(TelemetryStatus, "telemetry_status"),
        default=TelemetryStatus.UNKNOWN,
    )
    telemetry_source: Mapped[TelemetrySource] = mapped_column(
        _enum(TelemetrySource, "telemetry_source"),
        default=TelemetrySource.SIMULATED,
    )
    driver_id: Mapped[int | None] = mapped_column(
        ForeignKey("driver.id", ondelete="SET NULL"), default=None
    )
    route_id: Mapped[int | None] = mapped_column(
        ForeignKey("route.id", ondelete="SET NULL"), default=None
    )
    reported_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL"), default=None
    )
    tracker_device_id: Mapped[str | None] = mapped_column(
        String(128), default=None
    )
    is_stale: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[DataSource] = mapped_column(
        _enum(DataSource, "data_source"), default=DataSource.SIMULATED
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), init=False
    )


class DriverAssignment(TimestampMixin, Base):
    """Driver <-> vehicle assignment window."""

    __tablename__ = "driver_assignment"
    __table_args__ = (
        Index("ix_assignment_muni_start", "municipality_id", "starts_at"),
        Index("ix_assignment_driver", "driver_id"),
        Index("ix_assignment_vehicle", "vehicle_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    municipality_id: Mapped[int] = mapped_column(
        ForeignKey("municipality.id", ondelete="CASCADE")
    )
    driver_id: Mapped[int] = mapped_column(
        ForeignKey("driver.id", ondelete="CASCADE")
    )
    vehicle_id: Mapped[int] = mapped_column(
        ForeignKey("vehicle.id", ondelete="CASCADE")
    )
    starts_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=None
    )
    ends_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    assigned_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL"), default=None
    )
    source: Mapped[DataSource] = mapped_column(
        _enum(DataSource, "data_source"), default=DataSource.SIMULATED
    )
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Route(TimestampMixin, Base):
    __tablename__ = "route"
    __table_args__ = (
        Index(
            "ix_route_muni_status_date",
            "municipality_id",
            "status",
            "scheduled_for",
        ),
        Index(
            "ix_route_generated_from_prediction", "generated_from_prediction_id"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    municipality_id: Mapped[int] = mapped_column(
        ForeignKey("municipality.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(160))
    code: Mapped[str | None] = mapped_column(String(48), default=None)
    driver_id: Mapped[int | None] = mapped_column(
        ForeignKey("driver.id", ondelete="SET NULL"), default=None
    )
    vehicle_id: Mapped[int | None] = mapped_column(
        ForeignKey("vehicle.id", ondelete="SET NULL"), default=None
    )
    status: Mapped[RouteStatus] = mapped_column(
        _enum(RouteStatus, "route_status"), default=RouteStatus.DRAFT
    )
    scheduled_for: Mapped[datetime.date | None] = mapped_column(default=None)
    started_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    completed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    planned_distance_km: Mapped[float | None] = mapped_column(
        Float, default=None
    )
    actual_distance_km: Mapped[float | None] = mapped_column(
        Float, default=None
    )
    planned_duration_minutes: Mapped[int | None] = mapped_column(
        Integer, default=None
    )
    total_collected_kg: Mapped[float | None] = mapped_column(
        Float, default=None
    )
    #: Single, one-directional link between a recommendation and the route it
    #: produced. `prediction` therefore creates BEFORE `route`, and Prediction
    #: deliberately carries no FK back to `route` (that would make the create
    #: order cyclic and break the first PostgreSQL migration).
    generated_from_prediction_id: Mapped[int | None] = mapped_column(
        ForeignKey("prediction.id", ondelete="SET NULL"), default=None
    )
    approved_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL"), default=None
    )
    source: Mapped[DataSource] = mapped_column(
        _enum(DataSource, "data_source"), default=DataSource.SIMULATED
    )
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    stops: Mapped[list["RouteStop"]] = relationship(
        back_populates="route",
        cascade="all, delete-orphan",
        default_factory=list,
        order_by="RouteStop.sequence",
    )


class RouteStop(TimestampMixin, Base):
    __tablename__ = "route_stop"
    __table_args__ = (
        UniqueConstraint("route_id", "sequence", name="uq_route_stop_sequence"),
        Index("ix_route_stop_status", "route_id", "status"),
        Index("ix_route_stop_bin", "bin_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    route_id: Mapped[int] = mapped_column(
        ForeignKey("route.id", ondelete="CASCADE")
    )
    municipality_id: Mapped[int] = mapped_column(
        ForeignKey("municipality.id", ondelete="CASCADE")
    )
    sequence: Mapped[int] = mapped_column(Integer, default=1)
    bin_id: Mapped[int | None] = mapped_column(
        ForeignKey("bin.id", ondelete="SET NULL"), default=None
    )
    entity_id: Mapped[int | None] = mapped_column(
        ForeignKey("entity.id", ondelete="SET NULL"), default=None
    )
    status: Mapped[StopStatus] = mapped_column(
        _enum(StopStatus, "stop_status"), default=StopStatus.PENDING
    )
    latitude: Mapped[float | None] = mapped_column(Float, default=None)
    longitude: Mapped[float | None] = mapped_column(Float, default=None)
    eta: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    arrived_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    completed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    collected_kg: Mapped[float | None] = mapped_column(Float, default=None)
    skip_reason: Mapped[str | None] = mapped_column(Text, default=None)
    source: Mapped[DataSource] = mapped_column(
        _enum(DataSource, "data_source"), default=DataSource.SIMULATED
    )
    notes: Mapped[str | None] = mapped_column(Text, default=None)

    route: Mapped["Route"] = relationship(back_populates="stops", default=None)


# --------------------------------------------------------------------------
# Intelligence: predictions, alerts, reports
# --------------------------------------------------------------------------


class Prediction(TimestampMixin, Base):
    """Forecasts, anomaly scores and human-approved recommendations.

    Route recommendations are linked to the route they generated from the
    `route` side only (`Route.generated_from_prediction_id`); see the note
    on the columns below.
    """

    __tablename__ = "prediction"
    __table_args__ = (
        Index(
            "ix_prediction_muni_kind_time",
            "municipality_id",
            "kind",
            "created_at",
        ),
        Index("ix_prediction_bin", "bin_id"),
        Index("ix_prediction_approval", "approval_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    municipality_id: Mapped[int] = mapped_column(
        ForeignKey("municipality.id", ondelete="CASCADE")
    )
    kind: Mapped[PredictionKind] = mapped_column(
        _enum(PredictionKind, "prediction_kind")
    )
    bin_id: Mapped[int | None] = mapped_column(
        ForeignKey("bin.id", ondelete="SET NULL"), default=None
    )
    entity_id: Mapped[int | None] = mapped_column(
        ForeignKey("entity.id", ondelete="SET NULL"), default=None
    )
    vehicle_id: Mapped[int | None] = mapped_column(
        ForeignKey("vehicle.id", ondelete="SET NULL"), default=None
    )
    #: NOTE: no `route_id` FK here on purpose. A route generated from this
    #: recommendation points back via `route.generated_from_prediction_id`,
    #: keeping the metadata create order acyclic (bin/entity/vehicle ->
    #: prediction -> route). Tenant isolation is unchanged: both rows carry
    #: their own `municipality_id`.
    horizon_hours: Mapped[int | None] = mapped_column(Integer, default=None)
    predicted_for: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    predicted_value: Mapped[float | None] = mapped_column(Float, default=None)
    confidence: Mapped[float | None] = mapped_column(Float, default=None)
    method: Mapped[str | None] = mapped_column(String(120), default=None)
    explanation: Mapped[str | None] = mapped_column(Text, default=None)
    input_summary: Mapped[str | None] = mapped_column(Text, default=None)
    approval_status: Mapped[ApprovalStatus] = mapped_column(
        _enum(ApprovalStatus, "approval_status"), default=ApprovalStatus.PENDING
    )
    reviewed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL"), default=None
    )
    reviewed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    review_note: Mapped[str | None] = mapped_column(Text, default=None)
    source: Mapped[DataSource] = mapped_column(
        _enum(DataSource, "data_source"), default=DataSource.DERIVED
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Alert(TimestampMixin, Base):
    __tablename__ = "alert"
    __table_args__ = (
        Index(
            "ix_alert_muni_status_sev", "municipality_id", "status", "severity"
        ),
        Index("ix_alert_bin_time", "bin_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    municipality_id: Mapped[int] = mapped_column(
        ForeignKey("municipality.id", ondelete="CASCADE")
    )
    kind: Mapped[AlertKind] = mapped_column(_enum(AlertKind, "alert_kind"))
    severity: Mapped[AlertSeverity] = mapped_column(
        _enum(AlertSeverity, "alert_severity"), default=AlertSeverity.MEDIUM
    )
    status: Mapped[AlertStatus] = mapped_column(
        _enum(AlertStatus, "alert_status"), default=AlertStatus.OPEN
    )
    title: Mapped[str] = mapped_column(String(200), default="")
    message: Mapped[str | None] = mapped_column(Text, default=None)
    priority_score: Mapped[float | None] = mapped_column(Float, default=None)
    bin_id: Mapped[int | None] = mapped_column(
        ForeignKey("bin.id", ondelete="SET NULL"), default=None
    )
    sensor_id: Mapped[int | None] = mapped_column(
        ForeignKey("sensor.id", ondelete="SET NULL"), default=None
    )
    entity_id: Mapped[int | None] = mapped_column(
        ForeignKey("entity.id", ondelete="SET NULL"), default=None
    )
    vehicle_id: Mapped[int | None] = mapped_column(
        ForeignKey("vehicle.id", ondelete="SET NULL"), default=None
    )
    route_id: Mapped[int | None] = mapped_column(
        ForeignKey("route.id", ondelete="SET NULL"), default=None
    )
    prediction_id: Mapped[int | None] = mapped_column(
        ForeignKey("prediction.id", ondelete="SET NULL"), default=None
    )
    sensor_reading_id: Mapped[int | None] = mapped_column(
        ForeignKey("sensor_reading.id", ondelete="SET NULL"), default=None
    )
    acknowledged_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL"), default=None
    )
    acknowledged_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    resolved_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    resolution_note: Mapped[str | None] = mapped_column(Text, default=None)
    source: Mapped[DataSource] = mapped_column(
        _enum(DataSource, "data_source"), default=DataSource.DERIVED
    )


class Report(TimestampMixin, Base):
    __tablename__ = "report"
    __table_args__ = (
        Index(
            "ix_report_muni_kind_time", "municipality_id", "kind", "created_at"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    municipality_id: Mapped[int] = mapped_column(
        ForeignKey("municipality.id", ondelete="CASCADE")
    )
    kind: Mapped[ReportKind] = mapped_column(_enum(ReportKind, "report_kind"))
    export_format: Mapped[ReportFormat] = mapped_column(
        _enum(ReportFormat, "report_format"), default=ReportFormat.CSV
    )
    status: Mapped[ReportStatus] = mapped_column(
        _enum(ReportStatus, "report_status"), default=ReportStatus.QUEUED
    )
    title: Mapped[str] = mapped_column(String(200), default="")
    period_start: Mapped[datetime.date | None] = mapped_column(default=None)
    period_end: Mapped[datetime.date | None] = mapped_column(default=None)
    entity_id: Mapped[int | None] = mapped_column(
        ForeignKey("entity.id", ondelete="SET NULL"), default=None
    )
    waste_type_id: Mapped[int | None] = mapped_column(
        ForeignKey("waste_type.id", ondelete="SET NULL"), default=None
    )
    area_name: Mapped[str | None] = mapped_column(String(120), default=None)
    filters_summary: Mapped[str | None] = mapped_column(Text, default=None)
    row_count: Mapped[int | None] = mapped_column(Integer, default=None)
    file_name: Mapped[str | None] = mapped_column(String(255), default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)
    generated_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL"), default=None
    )
    generated_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    source: Mapped[DataSource] = mapped_column(
        _enum(DataSource, "data_source"), default=DataSource.DERIVED
    )


class AuditLog(Base):
    """Append-only audit history for every mutating action."""

    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_muni_time", "municipality_id", "created_at"),
        Index("ix_audit_entity_ref", "table_name", "record_id"),
        Index("ix_audit_user_time", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    municipality_id: Mapped[int | None] = mapped_column(
        ForeignKey("municipality.id", ondelete="SET NULL"), default=None
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL"), default=None
    )
    actor_label: Mapped[str | None] = mapped_column(String(255), default=None)
    actor_role: Mapped[UserRole | None] = mapped_column(
        _enum(UserRole, "user_role"), default=None
    )
    action: Mapped[AuditAction] = mapped_column(
        _enum(AuditAction, "audit_action"), default=AuditAction.UPDATE
    )
    table_name: Mapped[str] = mapped_column(String(80), default="")
    record_id: Mapped[int | None] = mapped_column(Integer, default=None)
    summary: Mapped[str | None] = mapped_column(Text, default=None)
    before_json: Mapped[str | None] = mapped_column(Text, default=None)
    after_json: Mapped[str | None] = mapped_column(Text, default=None)
    source: Mapped[DataSource] = mapped_column(
        _enum(DataSource, "data_source"), default=DataSource.MANUAL
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), init=False
    )
