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


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(SAEnum(UserRole), nullable=False, default=UserRole.field_rep)
    is_active = Column(Boolean, default=True, nullable=False)

    employee_id = Column(String(100))
    phone = Column(String(20), unique=True, nullable=True)
    imei = Column(String(50))
    activation_code = Column(String(10), nullable=True)
    is_registered = Column(Boolean, default=False, nullable=False)

    # Company profile — mandatory for non-admin users
    company_profile_id = Column(Integer, ForeignKey("company_profiles.id", ondelete="SET NULL"), nullable=True)

    # Payment settings (per-user, when invoicing module is enabled)
    payment_mode = Column(SAEnum(PaymentMode), nullable=True)
    denomination_mandatory = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Many-to-many positions
    positions = relationship("Position", secondary=user_positions, back_populates="users")
    company_profile = relationship("CompanyProfile", foreign_keys=[company_profile_id])
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


class UserModuleAccess(Base):
    __tablename__ = "user_module_access"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    module = Column(SAEnum(ModuleName), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "module"),)

    user = relationship("User", back_populates="module_access")
