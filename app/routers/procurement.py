from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload, selectinload

from app.dependencies import get_db, require_web_auth, require_restricted_module_web_access
from app.models.material_request import MaterialRequest, MRStatus
from app.models.procurement import (ProcurementItem, QCStatus, QuotationStatus,
                                    VendorQuotation, WorkOrder, WorkOrderStatus)
from app.models.recce import RecceInformation
from app.models.user import User, UserRole
from app.utils.flash import get_flash, set_flash_error, set_flash_success
from app.services.access_control import (
    require_recce_access,
    require_work_order_access,
    scope_quotation_query,
    scope_recce_query,
    scope_work_order_query,
)
from app.utils.pagination import paginate

router = APIRouter(prefix="/operations/procurement", tags=["procurement"])
templates = Jinja2Templates(directory="app/templates")


def _is_user_regional_or_higher(user: User) -> bool:
    """Returns True if user has Regional management scope or higher (Admin, or TM with level Region/Zone)."""
    if user.role == UserRole.admin:
        return True
    if user.role == UserRole.territory_manager:
        if user.geography and user.geography.level and user.geography.level.value in ["region", "zone"]:
            return True
    return False


@router.get("", response_class=HTMLResponse)
async def procurement_hub(
    request: Request,
    current_user: User = Depends(require_restricted_module_web_access),
    db: Session = Depends(get_db),
    tab: str = Query(default="work_orders"), # recce, quotations, work_orders
    status: str = Query(default=""),
    page: int = Query(default=1, ge=1),
):
    # 1. Recce Records Query
    recce_query = scope_recce_query(db.query(RecceInformation), current_user, db).options(
        joinedload(RecceInformation.material_request).joinedload(MaterialRequest.outlet)
    ).join(MaterialRequest, MaterialRequest.id == RecceInformation.material_request_id)
    # 2. Quotation Records Query
    quote_query = scope_quotation_query(
        db.query(VendorQuotation), current_user, db
    ).options(
        joinedload(VendorQuotation.vendor),
        joinedload(VendorQuotation.material_request).joinedload(MaterialRequest.outlet),
    ).join(MaterialRequest, MaterialRequest.id == VendorQuotation.material_request_id)
    # 3. Work Orders Query
    wo_query = scope_work_order_query(
        db.query(WorkOrder), current_user, db
    ).options(
        joinedload(WorkOrder.vendor), joinedload(WorkOrder.outlet),
        joinedload(WorkOrder.material_request).joinedload(MaterialRequest.outlet),
        selectinload(WorkOrder.progress_logs),
    ).outerjoin(MaterialRequest, MaterialRequest.id == WorkOrder.material_request_id)

    is_regional = _is_user_regional_or_higher(current_user)

    if tab == "recce":
        recce_query = recce_query.order_by(RecceInformation.created_at.desc())
        pagination = paginate(recce_query, page)
    elif tab == "quotations":
        if status:
            quote_query = quote_query.filter(VendorQuotation.status == status)
        quote_query = quote_query.order_by(VendorQuotation.created_at.desc())
        pagination = paginate(quote_query, page)
    else:
        tab = "work_orders"
        if status:
            wo_query = wo_query.filter(WorkOrder.status == status)
        wo_query = wo_query.order_by(WorkOrder.created_at.desc())
        pagination = paginate(wo_query, page)

    return templates.TemplateResponse("procurement/index.html", {
        "request": request,
        "current_user": current_user,
        "tab": tab,
        "status": status,
        "pagination": pagination,
        "is_regional": is_regional,
        "WorkOrderStatus": WorkOrderStatus,
        "QuotationStatus": QuotationStatus,
        "QCStatus": QCStatus,
        **get_flash(request),
    })


@router.post("/work-orders/{wo_id}/mark-paid")
async def mark_work_order_paid(
    wo_id: int,
    request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
    notes: Optional[str] = Form(default=None),
):
    """
    Transition Completed/Concluded Work Order to Paid status.
    Restricted to users >= Region.
    """
    if not _is_user_regional_or_higher(current_user):
        set_flash_error(request, "Permission denied: Transitioning Work Order status to Paid requires Regional scope or higher.")
        return RedirectResponse("/operations/procurement?tab=work_orders", status_code=302)

    try:
        wo = require_work_order_access(db, current_user, wo_id)
    except HTTPException:
        set_flash_error(request, "Work order not found.")
        return RedirectResponse("/operations/procurement?tab=work_orders", status_code=302)

    old_status = wo.status.value if hasattr(wo.status, "value") else str(wo.status)

    wo.status = WorkOrderStatus.paid
    if notes:
        wo.notes = (wo.notes or "") + f"\n[Payment Audit by {current_user.full_name}]: {notes}"
    db.commit()

    mr = wo.material_request or (wo.quotation.material_request if wo.quotation else None)
    if mr:
        from app.services.channel_partner_notification import record_material_request_history_log
        record_material_request_history_log(
            db=db,
            material_request_id=mr.id,
            action="work_order_paid",
            performed_by_id=current_user.id,
            old_status=old_status,
            new_status="Paid",
            vendor_id=wo.vendor_id,
            notes=f"Work Order {wo.wo_number} marked as Paid by Regional Manager {current_user.full_name}."
        )

    set_flash_success(request, f"Work Order {wo.wo_number} successfully marked as Paid.")
    return RedirectResponse("/operations/procurement?tab=work_orders", status_code=302)


def generate_vendor_batch_id(db: Session, vendor_id: int) -> str:
    """
    Generates auto-incrementing Batch ID for items produced under vendor's Work Orders.
    Format: VEND-{vendor_id}-BATCH-{seq:04d}
    """
    count = db.query(func.count(ProcurementItem.id)).filter(
        ProcurementItem.vendor_id == vendor_id
    ).scalar() or 0
    seq = count + 1
    return f"VEND-{vendor_id}-BATCH-{seq:04d}"


@router.post("/recces/{recce_id}/{action}")
async def review_recce_web(
    recce_id: int,
    action: str,
    request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
    reason: Optional[str] = Form(default=None),
):
    if not _is_user_regional_or_higher(current_user):
        set_flash_error(request, "Only L3/L4 regional managers may review Recce.")
        return RedirectResponse("/operations/procurement?tab=recce", status_code=302)
    try:
        recce = require_recce_access(db, current_user, recce_id, for_update=True)
    except HTTPException:
        recce = None
    if not recce or recce.status != "Submitted" or action not in {"approve", "reject"}:
        set_flash_error(request, "Recce is not awaiting this action.")
        return RedirectResponse("/operations/procurement?tab=recce", status_code=302)
    if action == "reject" and not (reason or "").strip():
        set_flash_error(request, "A rejection reason is required.")
        return RedirectResponse("/operations/procurement?tab=recce", status_code=302)
    recce.status = "Approved" if action == "approve" else "Rejected"
    recce.rejection_reason = reason.strip() if reason else None
    recce.approved_by_id = current_user.id
    recce.approved_at = datetime.utcnow()
    db.commit()
    set_flash_success(request, f"Recce {recce.status.lower()}.")
    return RedirectResponse("/operations/procurement?tab=recce", status_code=302)
