import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum as SAEnum
from app.models.base import Base


class WebhookEvent(str, enum.Enum):
    # Attendance & Timesheets
    attendance_checkin = "attendance.checkin"
    attendance_checkout = "attendance.checkout"
    timesheet_submitted = "timesheet.submitted"
    timesheet_approved = "timesheet.approved"

    # Operations & Finances
    order_created = "order.created"
    order_status_updated = "order.status_updated"
    payment_recorded = "payment.recorded"
    expense_submitted = "expense.submitted"
    expense_approved = "expense.approved"

    # Field Visits & Master Data
    visit_checkin = "visit.checkin"
    outlet_created = "outlet.created"

    # Procurement & Marketing Assets
    material_request_created = "material_request.created"
    material_request_approved = "material_request.approved"
    work_order_created = "work_order.created"
    work_order_qc_passed = "work_order.qc_passed"
    marketing_asset_created = "marketing_asset.created"


class SystemWebhook(Base):
    __tablename__ = "system_webhooks"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    event_type = Column(SAEnum(WebhookEvent), nullable=False)
    endpoint_url = Column(String(500), nullable=False)
    secret_key = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    last_triggered_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
