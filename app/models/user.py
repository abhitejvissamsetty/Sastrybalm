import enum

from sqlalchemy import (
    Boolean, Column, DateTime, Enum as SAEnum,
    ForeignKey, Integer, String, Table, UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    territory_manager = "territory_manager"
    field_rep = "field_rep"
    vendor_technician = "vendor_technician"
    vendor_admin = "vendor_admin"
    qc_manager = "qc_manager"


class ModuleName(str, enum.Enum):
    orders = "orders"
    inventory = "inventory"
    expenses = "expenses"
    timesheets = "timesheets"
    attendance = "attendance"
    visits = "visits"
    gps_map = "gps_map"
    analytics = "analytics"
    approvals = "approvals"
    settings = "settings"
    backup = "backup"
    invoicing = "invoicing"


class PaymentMode(str, enum.Enum):
    cash_only = "cash_only"
    online_only = "online_only"
    cash_and_online = "cash_and_online"


# Many-to-many: User ↔ Position
user_positions = Table(
    "user_positions",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("position_id", Integer, ForeignKey("positions.id"), primary_key=True),
)

# Many-to-many: User (QC Manager) ↔ Vendors
user_vendors = Table(
    "user_vendors",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("vendor_id", Integer, ForeignKey("vendors.id", ondelete="CASCADE"), primary_key=True),
)

# Many-to-many: User (Territory Manager) ↔ Warehouses
user_warehouses = Table(
    "user_warehouses",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("warehouse_id", Integer, ForeignKey("warehouses.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=True)
    role = Column(SAEnum(UserRole), nullable=False, default=UserRole.field_rep)
    is_active = Column(Boolean, default=True, nullable=False)
    token_version = Column(Integer, default=0, nullable=False)

    employee_id = Column(String(100))
    phone = Column(String(20), unique=True, nullable=True)
    imei = Column(String(50))
    activation_code = Column(String(10), nullable=True)
    is_registered = Column(Boolean, default=False, nullable=False)

    # Company profile — mandatory for non-admin users
    company_profile_id = Column(Integer, ForeignKey("company_profiles.id", ondelete="SET NULL"), nullable=True)

    # Role-specific scoped assignments
    geography_id = Column(Integer, ForeignKey("geographies.id", ondelete="SET NULL"), nullable=True)
    vendor_id = Column(Integer, ForeignKey("vendors.id", ondelete="SET NULL"), nullable=True)

    # Payment settings (per-user, when invoicing module is enabled)
    payment_mode = Column(SAEnum(PaymentMode), nullable=True)
    denomination_mandatory = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    positions = relationship("Position", secondary=user_positions, back_populates="users")
    company_profile = relationship("CompanyProfile", foreign_keys=[company_profile_id])
    geography = relationship("Geography", foreign_keys=[geography_id])
    vendor = relationship("Vendor", foreign_keys=[vendor_id])
    qc_vendors = relationship("Vendor", secondary=user_vendors)
    scoped_warehouses = relationship("Warehouse", secondary=user_warehouses)
    module_access = relationship(
        "UserModuleAccess", back_populates="user", cascade="all, delete-orphan"
    )

    # Phase 3 back-references
    orders = relationship("Order", back_populates="user", foreign_keys="Order.user_id")
    payments = relationship("Payment", back_populates="user", foreign_keys="Payment.user_id")
    expenses = relationship("Expense", back_populates="user", foreign_keys="Expense.user_id")
    timesheets = relationship("Timesheet", back_populates="user", foreign_keys="Timesheet.user_id")
    visit_records = relationship("VisitRecord", back_populates="user", foreign_keys="VisitRecord.user_id")
    material_requests = relationship("MaterialRequest", back_populates="user", foreign_keys="MaterialRequest.user_id")

    def display_role(self) -> str:
        return self.role.value.replace("_", " ").title()

    def active_modules(self) -> list[str]:
        return [ma.module.value for ma in self.module_access if ma.is_active]

    def position_names(self) -> str:
        if self.positions:
            return ", ".join(p.name for p in self.positions)
        return "—"

    @property
    def can_access_restricted_modules(self) -> bool:
        """
        Returns True ONLY IF:
          1. User is an Admin ('admin')
          2. OR User is a Territory Manager ('territory_manager') AND assigned geography level >= Region ('zone', 'region', 'country', 'national').
        For all other users (Field Reps, Vendor Techs, QC Managers, or TMs assigned below Region e.g. Territory level),
        Expenses, Timesheets, and Material Requests are completely removed and blocked.
        """
        role_val = getattr(self.role, "value", str(self.role or ""))
        if role_val == "admin":
            return True
        if role_val == "territory_manager":
            if not self.geography_id:
                return False
            try:
                if self.geography:
                    geo_level = getattr(self.geography.level, "value", str(self.geography.level or "")).lower()
                    return geo_level in ("zone", "region", "country", "national")
            except Exception:
                pass
        return False

    @property
    def level(self) -> str:
        """
        Returns highest position level ('L4', 'L3', 'L2', 'L1') for this user.
        Admin users default to 'L4'.
        """
        role_val = getattr(self.role, "value", str(self.role or "")).lower()
        if role_val == "admin":
            return "L4"

        levels = set()
        for pos in getattr(self, "positions", []):
            lvl = getattr(pos.level, "value", str(pos.level or "")).upper()
            if lvl in ("L1", "L2", "L3", "L4"):
                levels.add(lvl)

        if "L4" in levels:
            return "L4"
        if "L3" in levels:
            return "L3"
        if "L2" in levels:
            return "L2"
        if "L1" in levels:
            return "L1"

        if role_val == "territory_manager":
            return "L2"
        return "L1"

    def can_approve_leave_for(self, applicant: "User", db=None) -> bool:
        """
        Leave Approval Hierarchy Rules:
        - L1 & L2 leaves can be approved by L3 & L4 users (and Admin).
        - L3 leaves can ONLY be approved by L4 users (and Admin).
        - L1 & L2 users cannot approve any leaves.
        - L3 users cannot approve L3 or L4 leaves.
        """
        approver_lvl = self.level
        applicant_lvl = applicant.level if applicant else "L1"

        if approver_lvl in ("L1", "L2"):
            return False

        level_allowed = (
            approver_lvl == "L3" and applicant_lvl in ("L1", "L2")
        ) or approver_lvl == "L4"
        if not level_allowed:
            return False

        role_val = getattr(self.role, "value", str(self.role or "")).lower()
        if role_val == "admin":
            return True

        # Approvers may act only on users in their reporting-position subtree.
        approver_position_ids = {p.id for p in self.positions if p.is_active}
        if not approver_position_ids:
            return False
        for applicant_position in applicant.positions:
            curr = applicant_position.reporting_to
            visited = set()
            while curr and curr.id not in visited:
                if curr.id in approver_position_ids:
                    return True
                visited.add(curr.id)
                curr = curr.reporting_to
        return False


class UserModuleAccess(Base):
    __tablename__ = "user_module_access"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    module = Column(SAEnum(ModuleName), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "module"),)

    user = relationship("User", back_populates="module_access")
