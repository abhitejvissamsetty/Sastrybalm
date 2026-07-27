import json
import logging
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
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
    image: Optional[UploadFile] = File(default=None),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product or product.category_type != ProductCategory.marketing_procurement:
        set_flash_error(request, "Material requests can only be placed for 'Marketing - Procurement' items.")
        return RedirectResponse("/material-requests/new", status_code=302)

    image_url = None
    if image and image.filename:
        file_bytes = await image.read()
        if file_bytes:
            from app.utils.s3_service import upload_image_file
            image_url = upload_image_file(
                db=db,
                file_bytes=file_bytes,
                original_filename=image.filename,
                folder_prefix="material_requests",
                content_type=image.content_type or "image/jpeg",
                bucket_type="permanent",
            )

    import uuid
    mr = MaterialRequest(
        user_id=current_user.id,
        request_number=f"MR-MKTG-{uuid.uuid4().hex[:6].upper()}",
        status=MRStatus.submitted,
        item_details=json.dumps({"product_id": product.id, "product_name": product.name, "qty": quantity}),
        notes=notes or None,
        image_url=image_url,
    )
    db.add(mr)
    db.commit()

    set_flash_success(request, f"Material request {mr.request_number} created.")
    return RedirectResponse("/material-requests", status_code=302)


def _can_manage_vendor_mapping(user: User) -> bool:
    """Territory Managers whose geography level is >= Region (region or zone) or Admins can map vendors."""
    if user.role == UserRole.admin:
        return True
    if user.role == UserRole.territory_manager:
        if user.geography and user.geography.level and user.geography.level.value in ["region", "zone"]:
            return True
    return False


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
    available_vendors = db.query(User).filter(
        User.role.in_([UserRole.vendor_admin, UserRole.vendor_technician]),
        User.is_active == True
    ).order_by(User.full_name).all()

    can_map_vendor = _can_manage_vendor_mapping(current_user)

    return templates.TemplateResponse("material_requests/detail.html", {
        "request": request, "current_user": current_user,
        "item": item, "quotations": quotations, "available_vendors": available_vendors,
        "can_map_vendor": can_map_vendor,
        "MRStatus": MRStatus, "MRSyncStatus": MRSyncStatus,
        **get_flash(request),
    })


@router.post("/{mr_id}/assign-vendor")
async def mr_assign_vendor(
    mr_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
    vendor_id: Optional[str] = Form(default=None),
    notes: Optional[str] = Form(default=None),
):
    mr = db.query(MaterialRequest).filter(MaterialRequest.id == mr_id).first()
    if not mr:
        set_flash_error(request, "Material request not found.")
        return RedirectResponse("/material-requests", status_code=302)

    # Authority Check: TM must have Regional or Zonal management scope
    if not _can_manage_vendor_mapping(current_user):
        set_flash_error(request, "Vendor mapping requires Regional or Zonal management scope.")
        return RedirectResponse(f"/material-requests/{mr_id}", status_code=302)

    # Check if Work Order is already completed / QC approved
    for wo in mr.work_orders:
        if wo.qc_status == QCStatus.passed or wo.status == WorkOrderStatus.concluded:
            set_flash_error(request, "Cannot reassign vendor after QC Manager approval / Work Order completion.")
            return RedirectResponse(f"/material-requests/{mr_id}", status_code=302)

    v_id_int = int(vendor_id) if vendor_id and str(vendor_id).isdigit() else None
    vendor = db.query(User).filter(User.id == v_id_int).first() if v_id_int else None

    old_v_id = mr.vendor_id
    is_reassignment = old_v_id is not None and old_v_id != v_id_int
    mr.vendor_id = vendor.id if vendor else None
    db.commit()

    from app.services.channel_partner_notification import (
        record_material_request_history_log,
        trigger_vendor_material_request_notification,
    )
    v_name = vendor.full_name if vendor else "Unassigned"
    action_type = "vendor_reassigned" if is_reassignment else "vendor_assigned"
    record_material_request_history_log(
        db=db,
        material_request_id=mr.id,
        action=action_type,
        performed_by_id=current_user.id,
        old_status=mr.status.value if mr.status else None,
        new_status=mr.status.value if mr.status else None,
        vendor_id=mr.vendor_id,
        notes=notes or f"Material Request assigned to Vendor: '{v_name}' by {current_user.full_name}"
    )

    # Trigger notification to assigned vendor if MR is in an active/approved state
    if mr.vendor_id:
        trigger_vendor_material_request_notification(db, mr, is_reassignment=is_reassignment)

    set_flash_success(request, f"Vendor '{v_name}' assigned to Material Request {mr.mr_number}.")
    return RedirectResponse(f"/material-requests/{mr_id}", status_code=302)


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

    old_st = item.status.value if item.status else None
    if new_status in ["Approved", "Rejected", "Held", "approved", "rejected", "held"]:
        st_map = {"approved": MRStatus.acknowledged, "rejected": MRStatus.cancelled, "held": MRStatus.submitted}
        item.status = st_map.get(new_status.lower(), MRStatus.acknowledged)
        db.commit()

        from app.services.channel_partner_notification import (
            record_material_request_history_log,
            trigger_vendor_material_request_notification,
        )
        record_material_request_history_log(
            db=db,
            material_request_id=item.id,
            action="status_changed",
            performed_by_id=current_user.id,
            old_status=old_st,
            new_status=item.status.value,
            vendor_id=item.vendor_id,
            notes=f"Status updated from '{old_st}' to '{item.status.value}' by {current_user.full_name}"
        )

        # Notify vendor if approved
        if item.status == MRStatus.acknowledged and item.vendor_id:
            trigger_vendor_material_request_notification(db, item)

        set_flash_success(request, f"Material Request status updated to '{new_status.title()}'.")
    else:
        set_flash_error(request, f"Invalid status '{new_status}'.")

    return RedirectResponse(f"/material-requests/{mr_id}", status_code=302)


@router.post("/{mr_id}/quote")
async def mr_submit_quote(
    mr_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.vendor_admin, UserRole.vendor_technician)),
    db: Session = Depends(get_db),
    quote_amount: str = Form(...),
    lead_time_days: int = Form(7),
    notes: Optional[str] = Form(default=None),
    invoice_photo: Optional[UploadFile] = File(default=None),
):
    """Vendor places quotation on an Approved Material Request."""
    mr = db.query(MaterialRequest).filter(MaterialRequest.id == mr_id).first()
    if not mr:
        set_flash_error(request, "Material Request not found.")
        return RedirectResponse("/material-requests", status_code=302)

    invoice_photo_url = None
    if invoice_photo and invoice_photo.filename:
        file_bytes = await invoice_photo.read()
        if file_bytes:
            from app.utils.s3_service import upload_image_file
            invoice_photo_url = upload_image_file(
                db=db,
                file_bytes=file_bytes,
                original_filename=invoice_photo.filename,
                folder_prefix="vendor_invoices",
                content_type=invoice_photo.content_type or "image/jpeg",
                bucket_type="permanent",
            )

    quote = VendorQuotation(
        material_request_id=mr_id,
        vendor_id=current_user.id,
        quote_amount=Decimal(quote_amount),
        lead_time_days=lead_time_days,
        status=QuotationStatus.pending,
        notes=notes or None,
        invoice_photo_url=invoice_photo_url,
    )
    db.add(quote)
    db.commit()

    from app.services.channel_partner_notification import record_material_request_history_log
    record_material_request_history_log(
        db=db,
        material_request_id=mr.id,
        action="quotation_submitted",
        performed_by_id=current_user.id,
        old_status=mr.status.value,
        new_status=mr.status.value,
        vendor_id=current_user.id,
        notes=f"Quotation of ₹{Decimal(quote_amount):.2f} submitted by Vendor {current_user.full_name}"
    )

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

    mr = quote.material_request
    from app.services.channel_partner_notification import record_material_request_history_log

    if decision.lower() == "approved":
        quote.status = QuotationStatus.approved
        import uuid
        wo = WorkOrder(
            quotation_id=quote.id,
            material_request_id=mr_id,
            vendor_id=quote.vendor_id,
            wo_number=f"WO-{uuid.uuid4().hex[:6].upper()}",
            status=WorkOrderStatus.issued,
            qc_status=QCStatus.pending,
        )
        db.add(wo)
        if mr:
            mr.status = MRStatus.in_progress
        db.commit()

        record_material_request_history_log(
            db=db,
            material_request_id=mr_id,
            action="work_order_created",
            performed_by_id=current_user.id,
            old_status=mr.status.value if mr else None,
            new_status=MRStatus.in_progress.value,
            vendor_id=quote.vendor_id,
            notes=f"Quotation of ₹{quote.quote_amount:.2f} approved and Work Order {wo.wo_number} issued to Vendor."
        )
        set_flash_success(request, f"Quotation approved! Work Order {wo.wo_number} issued.")
    elif decision.lower() == "rejected":
        quote.status = QuotationStatus.rejected
        db.commit()
        record_material_request_history_log(
            db=db,
            material_request_id=mr_id,
            action="quotation_rejected",
            performed_by_id=current_user.id,
            notes=f"Quotation from Vendor rejected by {current_user.full_name}."
        )
        set_flash_success(request, "Quotation rejected.")
    else:
        quote.status = QuotationStatus.held
        db.commit()
        set_flash_success(request, "Quotation put on hold.")

    return RedirectResponse(f"/material-requests/{mr_id}", status_code=302)


from fastapi import File, UploadFile
import os
import shutil


@router.post("/work-orders/{wo_id}/qc")
async def work_order_qc(
    wo_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager, UserRole.qc_manager)),
    db: Session = Depends(get_db),
    qc_result: str = Form("passed"), # passed, failed
    qc_notes: Optional[str] = Form(default=None),
    qc_photo: Optional[UploadFile] = File(default=None),
):
    """Conclude Work Order, perform QC with Photo Inspection, Itemize Stock Inward, and Convert to Marketing Asset."""
    wo = db.query(WorkOrder).filter(WorkOrder.id == wo_id).first()
    if not wo:
        set_flash_error(request, "Work order not found.")
        return RedirectResponse("/material-requests", status_code=302)

    photo_path = None
    if qc_photo and qc_photo.filename:
        file_bytes = await qc_photo.read()
        if file_bytes:
            from app.utils.s3_service import upload_image_file
            photo_path = upload_image_file(
                db=db,
                file_bytes=file_bytes,
                original_filename=qc_photo.filename,
                folder_prefix="work_orders/qc",
                content_type=qc_photo.content_type or "image/jpeg",
                bucket_type="permanent",
            )

    if photo_path:
        wo.qc_photo_url = photo_path

    wo.qc_notes = qc_notes or None
    wo.qc_verified_at = datetime.utcnow()
    wo.qc_verified_by_id = current_user.id

    from app.services.channel_partner_notification import record_material_request_history_log
    mr = wo.material_request or (wo.quotation.material_request if wo.quotation else None)

    if qc_result.lower() == "passed":
        wo.qc_status = QCStatus.passed
        wo.status = WorkOrderStatus.concluded

        if mr:
            old_st = mr.status.value
            mr.status = MRStatus.completed
            record_material_request_history_log(
                db=db,
                material_request_id=mr.id,
                action="qc_approved",
                performed_by_id=current_user.id,
                old_status=old_st,
                new_status=MRStatus.completed.value,
                vendor_id=mr.vendor_id,
                notes=f"QC Verification Passed by {current_user.full_name} with photo inspection."
            )

            # Parse Material Request item details
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
                    # Itemised Stock Inward
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

                    # Convert to Marketing Asset
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
        if mr:
            record_material_request_history_log(
                db=db,
                material_request_id=mr.id,
                action="qc_failed",
                performed_by_id=current_user.id,
                old_status=mr.status.value,
                new_status=mr.status.value,
                vendor_id=mr.vendor_id,
                notes=f"QC Verification marked Failed by {current_user.full_name}."
            )
        db.commit()
        set_flash_error(request, f"Work Order {wo.wo_number} QC Marked as Failed.")

    mr_id = mr.id if mr else 1
    return RedirectResponse(f"/material-requests/{mr_id}", status_code=302)
