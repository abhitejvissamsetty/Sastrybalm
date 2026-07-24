import json
import logging
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_web_auth, require_web_roles
from app.models.material_request import MaterialRequest, MRStatus, MRSyncStatus
from app.models.product import Product, ProductCategory
from app.models.procurement import VendorQuotation, WorkOrder, QuotationStatus, WorkOrderStatus, QCStatus
from app.models.inventory import StockMovement
from app.models.asset_capitalization import AssetCapitalization, ACStatus
from app.models.user import User, UserRole
from app.utils.flash import get_flash, set_flash_error, set_flash_success
from app.utils.pagination import paginate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/material-requests", tags=["material_requests"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def mr_list(
    request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
    status: str = Query(default=""),
    user_id: str = Query(default=""),
    page: int = Query(default=1, ge=1),
):
    query = db.query(MaterialRequest)
    if current_user.role == UserRole.field_rep:
        query = query.filter(MaterialRequest.user_id == current_user.id)
    elif user_id:
        query = query.filter(MaterialRequest.user_id == int(user_id))
    if status:
        query = query.filter(MaterialRequest.status == status)
    query = query.order_by(MaterialRequest.created_at.desc())
    pagination = paginate(query, page)

    reps = []
    if current_user.role.value in ["admin", "territory_manager"]:
        reps = db.query(User).filter(User.role == UserRole.field_rep, User.is_active == True).order_by(User.full_name).all()

    return templates.TemplateResponse("material_requests/list.html", {
        "request": request, "current_user": current_user,
        "pagination": pagination, "status": status, "user_id": user_id,
        "reps": reps, "MRStatus": MRStatus, "MRSyncStatus": MRSyncStatus,
        **get_flash(request),
    })


@router.get("/new", response_class=HTMLResponse)
async def mr_new(
    request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
):
    # Filter products strictly to Marketing - Procurement category
    items = db.query(Product).filter(
        Product.is_active == True,
        Product.category_type == ProductCategory.marketing_procurement
    ).order_by(Product.name).all()

    return templates.TemplateResponse("material_requests/form.html", {
        "request": request, "current_user": current_user, "items": items, "error": None,
    })


@router.post("/new")
async def mr_create(
    request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
    product_id: int = Form(...),
    quantity: int = Form(...),
    notes: Optional[str] = Form(default=None),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product or product.category_type != ProductCategory.marketing_procurement:
        set_flash_error(request, "Material requests can only be placed for 'Marketing - Procurement' items.")
        return RedirectResponse("/material-requests/new", status_code=302)

    import uuid
    mr = MaterialRequest(
        user_id=current_user.id,
        request_number=f"MR-MKTG-{uuid.uuid4().hex[:6].upper()}",
        status=MRStatus.submitted,
        item_details=json.dumps({"product_id": product.id, "product_name": product.name, "qty": quantity}),
        notes=notes or None,
    )
    db.add(mr)
    db.commit()

    set_flash_success(request, f"Material request {mr.request_number} created.")
    return RedirectResponse("/material-requests", status_code=302)


@router.get("/{mr_id}", response_class=HTMLResponse)
async def mr_detail(
    mr_id: int, request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
):
    q = db.query(MaterialRequest).filter(MaterialRequest.id == mr_id)
    item = q.first()
    if not item:
        set_flash_error(request, "Material request not found.")
        return RedirectResponse("/material-requests", status_code=302)

    quotations = db.query(VendorQuotation).filter(VendorQuotation.material_request_id == mr_id).all()

    return templates.TemplateResponse("material_requests/detail.html", {
        "request": request, "current_user": current_user,
        "item": item, "quotations": quotations,
        "MRStatus": MRStatus, "MRSyncStatus": MRSyncStatus,
        **get_flash(request),
    })


@router.post("/{mr_id}/status")
async def mr_update_status(
    mr_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
    new_status: str = Form(...),
):
    item = db.query(MaterialRequest).filter(MaterialRequest.id == mr_id).first()
    if not item:
        set_flash_error(request, "Material request not found.")
        return RedirectResponse("/material-requests", status_code=302)

    if new_status in ["Approved", "Rejected", "Held", "approved", "rejected", "held"]:
        st_map = {"approved": MRStatus.approved, "rejected": MRStatus.rejected, "held": MRStatus.submitted}
        item.status = st_map.get(new_status.lower(), MRStatus.approved)
        db.commit()
        set_flash_success(request, f"Material Request status updated to '{new_status.title()}'.")
    else:
        set_flash_error(request, f"Invalid status '{new_status}'.")

    return RedirectResponse(f"/material-requests/{mr_id}", status_code=302)


@router.post("/{mr_id}/quote")
async def mr_submit_quote(
    mr_id: int, request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
    quote_amount: str = Form(...),
    lead_time_days: int = Form(7),
    notes: Optional[str] = Form(default=None),
):
    """Vendor places quotation on an Approved Material Request."""
    mr = db.query(MaterialRequest).filter(MaterialRequest.id == mr_id).first()
    if not mr:
        set_flash_error(request, "Material Request not found.")
        return RedirectResponse("/material-requests", status_code=302)

    quote = VendorQuotation(
        material_request_id=mr_id,
        vendor_id=current_user.id,
        quote_amount=Decimal(quote_amount),
        lead_time_days=lead_time_days,
        status=QuotationStatus.pending,
        notes=notes or None,
    )
    db.add(quote)
    db.commit()
    set_flash_success(request, "Quotation submitted successfully.")
    return RedirectResponse(f"/material-requests/{mr_id}", status_code=302)


@router.post("/{mr_id}/quote/{quote_id}/review")
async def quote_review(
    mr_id: int, quote_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
    decision: str = Form(...), # approved, rejected, held
):
    """Admin/Manager approves quotation and generates Work Order."""
    quote = db.query(VendorQuotation).filter(VendorQuotation.id == quote_id).first()
    if not quote:
        set_flash_error(request, "Quotation not found.")
        return RedirectResponse(f"/material-requests/{mr_id}", status_code=302)

    if decision.lower() == "approved":
        quote.status = QuotationStatus.approved
        import uuid
        wo = WorkOrder(
            quotation_id=quote.id,
            wo_number=f"WO-{uuid.uuid4().hex[:6].upper()}",
            status=WorkOrderStatus.issued,
            qc_status=QCStatus.pending,
        )
        db.add(wo)
        db.commit()
        set_flash_success(request, f"Quotation approved! Work Order {wo.wo_number} issued.")
    elif decision.lower() == "rejected":
        quote.status = QuotationStatus.rejected
        db.commit()
        set_flash_success(request, "Quotation rejected.")
    else:
        quote.status = QuotationStatus.held
        db.commit()
        set_flash_success(request, "Quotation put on hold.")

    return RedirectResponse(f"/material-requests/{mr_id}", status_code=302)


@router.post("/work-orders/{wo_id}/qc")
async def work_order_qc(
    wo_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
    qc_result: str = Form(...), # passed, failed
):
    """Conclude Work Order, perform QC, Itemize Stock Inward, and Convert to Marketing Asset."""
    wo = db.query(WorkOrder).filter(WorkOrder.id == wo_id).first()
    if not wo:
        set_flash_error(request, "Work order not found.")
        return RedirectResponse("/material-requests", status_code=302)

    if qc_result.lower() == "passed":
        wo.qc_status = QCStatus.passed
        wo.status = WorkOrderStatus.concluded

        # Parse Material Request item details
        mr = wo.quotation.material_request
        details = {}
        try:
            details = json.loads(mr.item_details or "{}")
        except Exception:
            pass

        prod_id = details.get("product_id")
        qty = details.get("qty", 1)

        if prod_id:
            prod = db.query(Product).filter(Product.id == prod_id).first()
            if prod:
                # 1. Itemised Stock Inward (adds to Marketing - Stock)
                prod.stock_qty += qty
                prod.category_type = ProductCategory.marketing_stock
                movement = StockMovement(
                    product_id=prod.id,
                    movement_type="INWARD",
                    quantity=qty,
                    reference_no=wo.wo_number,
                    notes="Work Order QC Verification Inward",
                    created_by_id=current_user.id,
                )
                db.add(movement)

                # 2. Automatically Convert to Marketing Asset
                import uuid
                asset = AssetCapitalization(
                    ac_number=f"AC-{uuid.uuid4().hex[:6].upper()}",
                    user_id=mr.user_id,
                    outlet_id=mr.outlet_id if mr.outlet_id else 1,
                    item_name=prod.name,
                    item_code=prod.sku or f"SKU-{prod.id}",
                    quantity=qty,
                    status=ACStatus.deployed,
                    notes=f"Converted from Work Order {wo.wo_number}",
                )
                db.add(asset)

        db.commit()
        set_flash_success(request, f"Work Order {wo.wo_number} QC Passed! Stock itemized and converted to Marketing Asset.")
    else:
        wo.qc_status = QCStatus.failed
        db.commit()
        set_flash_error(request, f"Work Order {wo.wo_number} QC Failed.")

    return RedirectResponse(f"/material-requests/{wo.quotation.material_request_id}", status_code=302)
