import enum
from datetime import date, datetime

from sqlalchemy import (Boolean, Column, Date, DateTime, Enum, ForeignKey, Integer,
                        Numeric, String, Text, func)
from sqlalchemy.orm import relationship

from app.models.base import Base
from app.utils.timezone import ist_now, ist_today


class OrderStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"
    confirmed = "confirmed"
    dispatched = "dispatched"
    delivered = "delivered"
    cancelled = "cancelled"


class OrderType(str, enum.Enum):
    primary = "Primary"
    secondary = "Secondary"


class FlowType(str, enum.Enum):
    zap_invoice = "zap_invoice"
    connect = "connect"


class SyncStatus(str, enum.Enum):
    not_applicable = "not_applicable"
    pending = "pending"
    synced = "synced"
    failed = "failed"


class PaymentSettlementStatus(str, enum.Enum):
    unpaid = "unpaid"
    partial = "partial"
    paid = "paid"


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    order_number = Column(String(30), unique=True, nullable=False, index=True)
    outlet_id = Column(Integer, ForeignKey("outlets.id", ondelete="RESTRICT"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    beat_id = Column(Integer, ForeignKey("beats.id", ondelete="SET NULL"), nullable=True)
    company_profile_id = Column(Integer, ForeignKey("company_profiles.id", ondelete="SET NULL"), nullable=True)
    channel_partner_id = Column(Integer, ForeignKey("local_channel_partners.id", ondelete="SET NULL"), nullable=True, index=True)
    order_type = Column(Enum(OrderType), default=OrderType.secondary, nullable=False)
    status = Column(Enum(OrderStatus), default=OrderStatus.draft, nullable=False)
    flow_type = Column(Enum(FlowType), default=FlowType.zap_invoice, nullable=False)
    sync_status = Column(Enum(SyncStatus), default=SyncStatus.not_applicable, nullable=False)
    payment_settlement = Column(
        Enum(PaymentSettlementStatus),
        default=PaymentSettlementStatus.unpaid,
        nullable=False,
    )
    connect_ref = Column(String(100), nullable=True)
    order_date = Column(Date, nullable=False, default=ist_today)
    notes = Column(Text, nullable=True)
    sync_error = Column(Text, nullable=True)
    sync_retries = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    is_archived = Column(Boolean, default=False, nullable=False, index=True)
    archived_at = Column(DateTime, nullable=True)

    outlet = relationship("Outlet", foreign_keys=[outlet_id])
    user = relationship("User", foreign_keys=[user_id], back_populates="orders")
    beat = relationship("Beat", foreign_keys=[beat_id])
    company_profile = relationship("CompanyProfile", foreign_keys=[company_profile_id])
    channel_partner = relationship("LocalChannelPartner", foreign_keys=[channel_partner_id])
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="order")
    history_logs = relationship("OrderHistoryLog", back_populates="order", cascade="all, delete-orphan", order_by="OrderHistoryLog.created_at.desc()")

    @property
    def subtotal(self) -> float:
        """Sum of line totals before GST."""
        return sum(item.line_total for item in self.items)

    @property
    def total_cgst(self) -> float:
        return sum(item.cgst_amount for item in self.items)

    @property
    def total_sgst(self) -> float:
        return sum(item.sgst_amount for item in self.items)

    @property
    def total_gst(self) -> float:
        return sum(item.gst_amount for item in self.items)

    @property
    def total_amount(self) -> float:
        """Grand total including GST."""
        return round(self.subtotal + self.total_gst, 2)

    @property
    def total_paid(self) -> float:
        """Sum of verified/collected payments against this order."""
        from app.models.payment import PaymentStatus
        return sum(
            float(p.amount)
            for p in self.payments
            if p.status in (PaymentStatus.collected, PaymentStatus.verified)
        )

    @property
    def balance_due(self) -> float:
        return round(self.total_amount - self.total_paid, 2)

    @property
    def item_count(self) -> int:
        return len(self.items)

    def status_badge_cls(self) -> str:
        return {
            OrderStatus.draft: "bg-slate-700 text-slate-300",
            OrderStatus.submitted: "bg-blue-900/50 text-blue-300",
            OrderStatus.confirmed: "bg-indigo-900/50 text-indigo-300",
            OrderStatus.dispatched: "bg-amber-900/50 text-amber-300",
            OrderStatus.delivered: "bg-emerald-900/50 text-emerald-300",
            OrderStatus.cancelled: "bg-red-900/50 text-red-300",
        }.get(self.status, "bg-slate-700 text-slate-300")

    def sync_badge_cls(self) -> str:
        return {
            SyncStatus.not_applicable: "bg-slate-700 text-slate-400",
            SyncStatus.pending: "bg-amber-900/50 text-amber-300",
            SyncStatus.synced: "bg-emerald-900/50 text-emerald-300",
            SyncStatus.failed: "bg-red-900/50 text-red-300",
        }.get(self.sync_status, "bg-slate-700 text-slate-300")

    def payment_badge_cls(self) -> str:
        return {
            PaymentSettlementStatus.unpaid: "bg-red-900/50 text-red-300",
            PaymentSettlementStatus.partial: "bg-amber-900/50 text-amber-300",
            PaymentSettlementStatus.paid: "bg-emerald-900/50 text-emerald-300",
        }.get(self.payment_settlement, "bg-slate-700 text-slate-300")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Numeric(10, 2), nullable=False)
    gst_rate = Column(Numeric(5, 2), nullable=False, default=0)
    discount_pct = Column(Numeric(5, 2), nullable=False, default=0)

    is_archived = Column(Boolean, default=False, nullable=False, index=True)
    archived_at = Column(DateTime, nullable=True)

    order = relationship("Order", back_populates="items")
    product = relationship("Product", foreign_keys=[product_id])

    @property
    def line_total_with_gst(self) -> float:
        """Line total including GST (i.e. base amount after discount)."""
        base = float(self.unit_price) * self.quantity
        discount = base * float(self.discount_pct) / 100
        return round(base - discount, 2)

    @property
    def line_total(self) -> float:
        """Base amount after discount, excluding GST."""
        return round(self.line_total_with_gst / (1 + float(self.gst_rate) / 100), 2)

    @property
    def gst_amount(self) -> float:
        """Total GST on this line item."""
        return round(self.line_total_with_gst - self.line_total, 2)

    @property
    def cgst_amount(self) -> float:
        """Central GST (half of total GST for intra-state)."""
        return round(self.gst_amount / 2, 2)

    @property
    def sgst_amount(self) -> float:
        """State GST (half of total GST for intra-state)."""
        return round(self.gst_amount - self.cgst_amount, 2)  # avoids rounding drift


class OrderHistoryLog(Base):
    __tablename__ = "order_history_logs"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    action = Column(String(100), nullable=False)  # e.g. 'created', 'status_changed', 'channel_partner_allocated'
    old_status = Column(String(50), nullable=True)
    new_status = Column(String(50), nullable=True)
    channel_partner_id = Column(Integer, ForeignKey("local_channel_partners.id", ondelete="SET NULL"), nullable=True)
    performed_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    order = relationship("Order", back_populates="history_logs")
    channel_partner = relationship("LocalChannelPartner", foreign_keys=[channel_partner_id])
    performed_by = relationship("User", foreign_keys=[performed_by_id])
