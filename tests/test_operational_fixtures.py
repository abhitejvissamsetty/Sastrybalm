from app.models.asset_capitalization import ACStatus
from app.models.expense import ExpenseStatus
from app.models.leave import LeaveStatus
from app.models.material_request import MRStatus
from app.models.order import OrderStatus
from app.models.payment import PaymentStatus
from app.models.procurement import QCStatus, QuotationStatus, WorkOrderStatus
from app.models.timesheet import TimesheetApproval, TimesheetStatus


def test_operational_fixture_links_every_required_domain(operational_data):
    records = operational_data

    assert records["order"].status == OrderStatus.delivered
    assert records["order"].visit is records["visit"]
    assert records["order"].items[0].line_total_with_gst == 590
    assert records["payment"].order is records["order"]
    assert records["payment"].status == PaymentStatus.verified
    assert records["visit"].timesheet is records["timesheet"]
    assert records["timesheet"].status == TimesheetStatus.closed
    assert records["timesheet"].approval_status == TimesheetApproval.approved
    assert records["expense"].status == ExpenseStatus.approved
    assert records["leave"].status == LeaveStatus.approved

    assert records["material_request"].status == MRStatus.work_order_issued
    assert records["recce"].material_request is records["material_request"]
    assert records["quotation"].recce is records["recce"]
    assert records["quotation"].status == QuotationStatus.approved
    assert records["work_order"].quotation is records["quotation"]
    assert records["work_order"].status == WorkOrderStatus.completed
    assert records["work_order"].qc_status == QCStatus.passed
    assert records["procurement_item"].work_order is records["work_order"]
    assert records["asset"].procurement_item is records["procurement_item"]
    assert records["asset"].status == ACStatus.deployed
    assert records["maintenance"].asset is records["asset"]
    assert records["maintenance"].progress_percent == 100
