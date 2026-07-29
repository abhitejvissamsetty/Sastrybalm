import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload, selectinload

from app.dependencies import get_db, require_api_auth
from app.models.asset_capitalization import (
    ACStatus, ACSyncStatus, AssetCapitalization, AssetMaintenanceLog,
    MaintenanceProgressLog,
)
from app.models.material_request import MaterialRequest, MRStatus
from app.models.outlet import Outlet
from app.models.procurement import (
    ProcurementAttachment, ProcurementItem, QCReport, QuotationStatus,
    VendorQuotation, WorkOrder, WorkOrderProgressLog, WorkOrderStatus,
)
from app.models.recce import RecceInformation
from app.models.user import User, UserRole
from app.models.vendor import Vendor
from app.services.access_control import (
    require_asset_access,
    require_maintenance_access,
    require_material_request_access,
    require_procurement_item_access,
    require_quotation_access,
    require_recce_access,
    require_vendor_access,
    require_work_order_access,
    scope_material_request_query,
    scope_asset_query,
    scope_maintenance_query,
    scope_procurement_item_query,
    scope_vendor_query,
    scope_work_order_query,
)
from app.services.idempotency import idempotent

router = APIRouter(prefix="/api/v1/procurement", tags=["procurement-workflow"])

# ── Schemas ───────────────────────────────────────────────────────────────────

class RecceCreateRequest(BaseModel):
    dimensions: Optional[str] = None
    dimension_length: Optional[float] = None
    dimension_width: Optional[float] = None
    dimension_height: Optional[float] = None
    dimension_depth: Optional[float] = None
    dimension_unit: str = "cm"
    description: str
    location_notes: Optional[str] = None
    image_urls: List[str] = Field(default_factory=list)
    material_specifications: Optional[str] = None
    client_notes: Optional[str] = None
    photo_url: Optional[str] = None

class QuotationCreateRequest(BaseModel):
    material_request_id: int
    recce_id: Optional[int] = None
    quote_amount: Optional[float] = None
    base_amount: float
    gst_percent: Optional[float] = None
    lead_time_days: int = 7
    notes: Optional[str] = None
    counter_recce_notes: Optional[str] = None

class WorkOrderQcSubmitRequest(BaseModel):
    manufactured_photo_url: Optional[str] = None
    notes: Optional[str] = None

class QcCompletionRequest(BaseModel):
    final_dimensions: str
    final_specifications: str
    qc_notes: str
    maintenance_schedule: Optional[str] = None
    image_urls: List[str] = Field(default_factory=list)

class AssetFromItemRequest(BaseModel):
    notes: Optional[str] = None
    image_url: Optional[str] = None

class MaintenanceLogRequest(BaseModel):
    notes: str
    photo_url: Optional[str] = None
    image_urls: List[str] = Field(default_factory=list)

class ReviewRequest(BaseModel):
    reason: Optional[str] = None

class ProgressRequest(BaseModel):
    progress_percent: int
    remarks: Optional[str] = None
    image_urls: List[str] = Field(default_factory=list)


def _role(user: User) -> str:
    return getattr(user.role, "value", str(user.role))


def _is_l3_l4(user: User) -> bool:
    return _role(user) == UserRole.admin.value or (
        _role(user) == UserRole.territory_manager.value and getattr(user, "level", "") in {"L3", "L4"}
    )


def _require_roles(user: User, *roles: str) -> None:
    if _role(user) not in roles and _role(user) != UserRole.admin.value:
        raise HTTPException(status_code=403, detail="This action is not available for your role.")


def _require_vendor_record(user: User, vendor_id: Optional[int]) -> None:
    if _role(user) in {UserRole.vendor_admin.value, UserRole.vendor_technician.value}:
        if not user.vendor_id or user.vendor_id != vendor_id:
            raise HTTPException(status_code=403, detail="Record belongs to another Vendor.")
    if _role(user) == UserRole.qc_manager.value and user.qc_vendors:
        if vendor_id not in {v.id for v in user.qc_vendors}:
            raise HTTPException(status_code=403, detail="Vendor is outside your QC assignment.")


def _attachments(db: Session, entity_type: str, entity_id: int, attachment_type: str, urls: List[str], user_id: int) -> None:
    for url in urls:
        if url and url.strip():
            db.add(ProcurementAttachment(
                entity_type=entity_type, entity_id=entity_id,
                attachment_type=attachment_type, file_url=url.strip(),
                uploaded_by_id=user_id,
            ))

# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/attachments/upload")
async def upload_procurement_attachment(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_api_auth),
):
    allowed = {"image/jpeg", "image/png", "image/webp"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail="Only JPG, PNG, and WEBP images are accepted.")
    contents = await file.read()
    if not contents or len(contents) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image must be non-empty and no larger than 5 MB.")
    from app.utils.s3_service import upload_image_file
    url = upload_image_file(
        db=db, file_bytes=contents, original_filename=file.filename or "evidence.jpg",
        folder_prefix="procurement", content_type=file.content_type,
    )
    return {"file_url": url}

@router.get("/material-requests")
def list_procurement_material_requests(
    status_filter: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_api_auth),
):
    query = scope_material_request_query(
        db.query(MaterialRequest).options(
            joinedload(MaterialRequest.product),
            joinedload(MaterialRequest.outlet),
            selectinload(MaterialRequest.recces),
        ), current_user, db
    )
    if status_filter:
        query = query.filter(MaterialRequest.status == status_filter)
    total = query.count()
    records = query.order_by(MaterialRequest.created_at.desc()).offset(
        (page - 1) * per_page
    ).limit(per_page).all()
    confidential = _role(current_user) in {
        UserRole.admin.value, UserRole.territory_manager.value,
        UserRole.vendor_admin.value, UserRole.vendor_technician.value,
        UserRole.qc_manager.value,
    }
    return {"page": page, "per_page": per_page, "total": total, "items": [{
        "id": mr.id, "mr_number": mr.mr_number, "status": mr.status.value,
        "description": mr.description, "product_name": mr.product.name if mr.product else mr.category,
        "approx_dimensions": mr.approx_dimensions,
        "outlet": {
            "id": mr.outlet.id, "name": mr.outlet.name, "address": mr.outlet.address,
            "gps_lat": mr.outlet.gps_lat, "gps_lng": mr.outlet.gps_lng,
        } if mr.outlet else None,
        "recce": ({
            "id": mr.recces[-1].id, "status": mr.recces[-1].status,
            "dimensions": mr.recces[-1].dimensions,
        } if confidential and mr.recces else None),
    } for mr in records]}

@router.post("/material-requests/{mr_id}/assign-vendor")
def assign_vendor(
    mr_id: int,
    vendor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_api_auth),
):
    if not _is_l3_l4(current_user):
        raise HTTPException(status_code=403, detail="Only L3/L4 managers may assign Vendors.")
    mr = require_material_request_access(db, current_user, mr_id)

    vendor = require_vendor_access(db, current_user, vendor_id)
    if vendor.status != "active":
        raise HTTPException(status_code=404, detail="Vendor not found")

    mr.vendor_id = vendor_id
    mr.status = MRStatus.vendor_assigned
    db.commit()
    db.refresh(mr)
    return {"message": "Vendor assigned successfully", "material_request_id": mr.id, "vendor_id": vendor_id, "status": mr.status.value}


@router.post("/material-requests/{mr_id}/recce")
@idempotent("procurement.recce.create")
def submit_recce(
    mr_id: int,
    req: RecceCreateRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_api_auth),
):
    _require_roles(current_user, UserRole.vendor_technician.value)
    mr = require_material_request_access(db, current_user, mr_id)
    if not mr.vendor_id:
        raise HTTPException(status_code=409, detail="A Vendor must be assigned before Recce.")
    _require_vendor_record(current_user, mr.vendor_id)
    if mr.status not in {MRStatus.vendor_assigned, MRStatus.recce_completed}:
        raise HTTPException(status_code=409, detail="Material Request is not awaiting Recce.")
    dimensions = [req.dimension_length, req.dimension_width, req.dimension_height, req.dimension_depth]
    if any(value is not None and value <= 0 for value in dimensions):
        raise HTTPException(status_code=400, detail="Every supplied dimension must be positive.")
    if len(req.image_urls) != 2:
        raise HTTPException(status_code=400, detail="Exactly two Recce images are required.")
    previous_count = db.query(RecceInformation).filter(RecceInformation.material_request_id == mr.id).count()

    recce = RecceInformation(
        material_request_id=mr.id,
        vendor_id=mr.vendor_id,
        created_by_id=current_user.id,
        dimensions=req.dimensions,
        dimension_length=req.dimension_length, dimension_width=req.dimension_width,
        dimension_height=req.dimension_height, dimension_depth=req.dimension_depth,
        dimension_unit=req.dimension_unit, description=req.description.strip(),
        location_notes=req.location_notes, status="Submitted", version=previous_count + 1,
        material_specifications=req.material_specifications,
        client_notes=req.client_notes,
        photo_url=req.image_urls[0],
    )
    db.add(recce)
    db.flush()
    _attachments(db, "recce", recce.id, "recce_image", req.image_urls, current_user.id)
    mr.status = MRStatus.recce_completed
    db.commit()
    db.refresh(recce)
    return {"message": "Recce Information submitted successfully", "recce_id": recce.id, "mr_status": mr.status.value}


@router.post("/recces/{recce_id}/approve")
def approve_recce(
    recce_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_api_auth),
):
    if not _is_l3_l4(current_user):
        raise HTTPException(status_code=403, detail="Only L3/L4 managers may approve Recce.")
    recce = require_recce_access(db, current_user, recce_id, for_update=True)
    if recce.status != "Submitted":
        raise HTTPException(status_code=409, detail="Only a Submitted Recce can be approved.")
    recce.status = "Approved"
    recce.approved_by_id = current_user.id
    recce.approved_at = datetime.utcnow()
    db.commit()
    return {"id": recce.id, "status": recce.status}


@router.post("/recces/{recce_id}/reject")
def reject_recce(
    recce_id: int,
    req: ReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_api_auth),
):
    if not _is_l3_l4(current_user):
        raise HTTPException(status_code=403, detail="Only L3/L4 managers may reject Recce.")
    if not req.reason or not req.reason.strip():
        raise HTTPException(status_code=400, detail="Rejection reason is required.")
    recce = require_recce_access(db, current_user, recce_id, for_update=True)
    if recce.status != "Submitted":
        raise HTTPException(status_code=409, detail="Recce is not awaiting review.")
    recce.status = "Rejected"
    recce.rejection_reason = req.reason.strip()
    recce.approved_by_id = current_user.id
    recce.approved_at = datetime.utcnow()
    db.commit()
    return {"id": recce.id, "status": recce.status}


@router.get("/material-requests/{mr_id}/recce")
def get_recce(
    mr_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_api_auth),
):
    require_material_request_access(db, current_user, mr_id)
    recce = db.query(RecceInformation).filter(RecceInformation.material_request_id == mr_id).order_by(RecceInformation.created_at.desc()).first()
    if not recce:
        raise HTTPException(status_code=404, detail="Recce information not found for this Material Request")
    return {
        "id": recce.id,
        "material_request_id": recce.material_request_id,
        "dimensions": recce.dimensions,
        "material_specifications": recce.material_specifications,
        "client_notes": recce.client_notes,
        "photo_url": recce.photo_url,
        "created_at": recce.created_at.isoformat(),
    }


@router.post("/quotations")
@idempotent("procurement.quotation.create")
def create_quotation(
    req: QuotationCreateRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_api_auth),
):
    _require_roles(current_user, UserRole.vendor_admin.value)
    mr = require_material_request_access(db, current_user, req.material_request_id)
    if not mr.vendor_id:
        raise HTTPException(status_code=409, detail="Material Request has no assigned Vendor.")
    _require_vendor_record(current_user, mr.vendor_id)
    recce = db.query(RecceInformation).filter(
        RecceInformation.material_request_id == mr.id,
        RecceInformation.status == "Approved",
    ).order_by(RecceInformation.version.desc()).first()
    if not recce:
        raise HTTPException(status_code=409, detail="An approved Recce is required before Quotation.")
    if req.base_amount <= 0:
        raise HTTPException(status_code=400, detail="Base amount must be positive.")
    gst_percent = req.gst_percent
    if gst_percent is None:
        gst_percent = float(mr.product.gst_rate or 0) if mr.product else 0
    if gst_percent < 0 or gst_percent > 100:
        raise HTTPException(status_code=400, detail="GST percentage must be between 0 and 100.")
    gst_amount = round(req.base_amount * gst_percent / 100, 2)
    total_amount = round(req.base_amount + gst_amount, 2)
    quote = VendorQuotation(
        material_request_id=mr.id,
        vendor_id=mr.vendor_id,
        recce_id=recce.id,
        quote_amount=total_amount,
        base_amount=req.base_amount, gst_percent=gst_percent,
        gst_amount=gst_amount, total_amount=total_amount,
        lead_time_days=req.lead_time_days,
        notes=req.notes,
        counter_recce_notes=req.counter_recce_notes,
        status=QuotationStatus.pending,
        submitted_at=datetime.utcnow(),
    )
    db.add(quote)
    mr.status = MRStatus.quotation_submitted
    db.commit()
    db.refresh(quote)
    return {"message": "Supplier Quotation submitted successfully", "quotation_id": quote.id, "status": quote.status.value}


@router.post("/quotations/{quote_id}/approve")
def approve_quotation(
    quote_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_api_auth),
):
    if not _is_l3_l4(current_user):
        raise HTTPException(status_code=403, detail="Only L3/L4 managers may approve Quotations.")
    quote = require_quotation_access(db, current_user, quote_id, for_update=True)

    existing_wo = db.query(WorkOrder).filter(WorkOrder.quotation_id == quote.id).first()
    if existing_wo:
        return {"message": "Work Order already exists", "work_order_id": existing_wo.id, "wo_number": existing_wo.wo_number}
    if quote.status != QuotationStatus.pending:
        raise HTTPException(status_code=409, detail="Quotation is not awaiting approval.")
    quote.status = QuotationStatus.approved
    quote.approved_by_id = current_user.id
    quote.approved_at = datetime.utcnow()
    mr = quote.material_request
    if mr:
        mr.status = MRStatus.work_order_issued

    # Create Work Order
    wo_num = f"WO-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
    wo = WorkOrder(
        quotation_id=quote.id,
        material_request_id=quote.material_request_id,
        vendor_id=quote.vendor_id,
        outlet_id=mr.outlet_id if mr else None,
        wo_number=wo_num,
        status=WorkOrderStatus.assigned,
    )
    db.add(wo)
    db.commit()
    db.refresh(wo)
    return {"message": "Quotation approved & Work Order created successfully", "work_order_id": wo.id, "wo_number": wo.wo_number}


@router.post("/quotations/{quote_id}/reject")
def reject_quotation(
    quote_id: int,
    req: ReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_api_auth),
):
    if not _is_l3_l4(current_user):
        raise HTTPException(status_code=403, detail="Only L3/L4 managers may reject Quotations.")
    if not req.reason or not req.reason.strip():
        raise HTTPException(status_code=400, detail="Rejection reason is required.")
    quote = require_quotation_access(db, current_user, quote_id, for_update=True)
    if quote.status != QuotationStatus.pending:
        raise HTTPException(status_code=409, detail="Quotation is not awaiting review.")
    quote.status = QuotationStatus.rejected
    quote.rejection_reason = req.reason.strip()
    quote.approved_by_id = current_user.id
    quote.approved_at = datetime.utcnow()
    db.commit()
    return {"id": quote.id, "status": quote.status.value}


@router.post("/work-orders/{wo_id}/submit-qc")
def submit_work_order_qc(
    wo_id: int,
    req: WorkOrderQcSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_api_auth),
):
    _require_roles(current_user, UserRole.vendor_admin.value)
    wo = require_work_order_access(db, current_user, wo_id)
    _require_vendor_record(current_user, wo.vendor_id)
    if wo.status not in {WorkOrderStatus.acknowledged, WorkOrderStatus.in_manufacturing}:
        raise HTTPException(status_code=409, detail="Only an Acknowledged Work Order can enter QC.")

    wo.status = WorkOrderStatus.qc_pending
    wo.progress_percent = 100
    if req.manufactured_photo_url:
        wo.manufactured_photo_url = req.manufactured_photo_url
    if req.notes:
        wo.notes = req.notes

    if wo.material_request:
        wo.material_request.status = MRStatus.qc_pending

    db.commit()
    db.refresh(wo)
    return {"message": "Work Order status updated to QC Pending", "work_order_id": wo.id, "status": wo.status.value}


@router.post("/work-orders/{wo_id}/acknowledge")
def acknowledge_work_order(
    wo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_api_auth),
):
    _require_roles(current_user, UserRole.vendor_admin.value)
    wo = require_work_order_access(db, current_user, wo_id, for_update=True)
    _require_vendor_record(current_user, wo.vendor_id)
    if wo.status not in {WorkOrderStatus.assigned, WorkOrderStatus.issued}:
        raise HTTPException(status_code=409, detail="Only an Assigned Work Order can be acknowledged.")
    wo.status = WorkOrderStatus.acknowledged
    wo.acknowledged_by_id = current_user.id
    wo.acknowledged_at = datetime.utcnow()
    db.commit()
    return {"id": wo.id, "status": wo.status.value}


@router.post("/work-orders/{wo_id}/progress")
@idempotent("procurement.work_order.progress")
def report_work_order_progress(
    wo_id: int,
    req: ProgressRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_api_auth),
):
    _require_roles(current_user, UserRole.vendor_admin.value, UserRole.qc_manager.value)
    if req.progress_percent < 0 or req.progress_percent > 100:
        raise HTTPException(status_code=400, detail="Progress must be between 0 and 100.")
    wo = require_work_order_access(db, current_user, wo_id, for_update=True)
    _require_vendor_record(current_user, wo.vendor_id)
    is_qc_return = _role(current_user) == UserRole.qc_manager.value and wo.status == WorkOrderStatus.qc_pending
    if not is_qc_return and wo.status not in {WorkOrderStatus.acknowledged, WorkOrderStatus.in_manufacturing}:
        raise HTTPException(status_code=409, detail="Work Order is not accepting progress reports.")
    if not is_qc_return and req.progress_percent < wo.progress_percent:
        raise HTTPException(status_code=409, detail="Vendor progress cannot decrease.")
    if is_qc_return and (req.progress_percent >= 100 or not req.remarks):
        raise HTTPException(status_code=400, detail="QC return requires progress below 100 and a remark.")
    wo.progress_percent = req.progress_percent
    wo.status = WorkOrderStatus.qc_pending if req.progress_percent == 100 else WorkOrderStatus.acknowledged
    log = WorkOrderProgressLog(
        work_order_id=wo.id, progress_percent=req.progress_percent,
        remarks=req.remarks, reported_by_id=current_user.id,
    )
    db.add(log)
    db.flush()
    _attachments(db, "work_order_progress", log.id, "progress_image", req.image_urls, current_user.id)
    db.commit()
    return {"id": wo.id, "status": wo.status.value, "progress_percent": wo.progress_percent}


@router.post("/work-orders/{wo_id}/qc-complete")
@idempotent("procurement.qc.complete")
def complete_qc_work_order(
    wo_id: int,
    req: QcCompletionRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_api_auth),
):
    _require_roles(current_user, UserRole.qc_manager.value)
    if len(req.image_urls) != 2:
        raise HTTPException(status_code=400, detail="Exactly two QC images are required.")
    wo = require_work_order_access(db, current_user, wo_id, for_update=True)
    _require_vendor_record(current_user, wo.vendor_id)
    existing = db.query(ProcurementItem).filter(
        ProcurementItem.work_order_id == wo.id,
        ProcurementItem.status != "Invalidated",
    ).first()
    if existing:
        return {"message": "QC Item already exists", "item_id": existing.id, "batch_number": existing.batch_number}
    if wo.status != WorkOrderStatus.qc_pending:
        raise HTTPException(status_code=409, detail="Only a QC Pending Work Order can be completed.")
    if not wo.vendor_id or not wo.material_request or not wo.material_request.product_id:
        raise HTTPException(status_code=409, detail="Work Order is missing Vendor, Material Request, or Product.")
    vendor = db.query(Vendor).filter(Vendor.id == wo.vendor_id).with_for_update().first()
    if not vendor:
        raise HTTPException(status_code=409, detail="Assigned Vendor no longer exists.")
    from app.routers.api.operations import resolve_l3_warehouse_for_order
    warehouse_id = resolve_l3_warehouse_for_order(
        current_user, wo.outlet_id, wo.material_request.outlet.beat_id if wo.material_request.outlet else None, db
    )
    if not warehouse_id:
        raise HTTPException(status_code=409, detail="No L3 regional warehouse could be resolved.")

    wo.status = WorkOrderStatus.completed
    wo.qc_verified_by_id = current_user.id
    wo.qc_verified_at = datetime.utcnow()
    wo.qc_notes = req.qc_notes

    if wo.material_request:
        wo.material_request.status = MRStatus.completed

    qc_report = QCReport(
        work_order_id=wo.id, status="Passed", remark=req.qc_notes.strip(),
        maintenance_schedule=req.maintenance_schedule, reported_by_id=current_user.id,
    )
    db.add(qc_report)
    db.flush()
    _attachments(db, "qc_report", qc_report.id, "qc_image", req.image_urls, current_user.id)

    prefix = vendor.batch_prefix or f"VEND-{vendor.id}"
    sequence = vendor.next_batch_sequence or 1
    batch_num = f"{prefix}-BATCH-{sequence:06d}"
    vendor.next_batch_sequence = sequence + 1
    mr = wo.material_request
    item_name = mr.product.name
    
    item = ProcurementItem(
        work_order_id=wo.id,
        product_id=mr.product_id, warehouse_id=warehouse_id,
        qc_report_id=qc_report.id, vendor_id=wo.vendor_id,
        outlet_id=wo.outlet_id or mr.outlet_id,
        item_name=item_name,
        batch_number=batch_num,
        final_dimensions=req.final_dimensions,
        final_specifications=req.final_specifications,
        qc_notes=req.qc_notes,
        qc_manager_id=current_user.id,
        status="Ready",
    )
    db.add(item)
    from app.services.inventory_service import record_stock_movement
    record_stock_movement(
        db=db,
        product_id=mr.product_id,
        warehouse_id=warehouse_id,
        movement_type="INWARD",
        quantity=1,
        reference_no=batch_num,
        notes=f"QC completed for {wo.wo_number}",
        created_by_id=current_user.id,
        commit=False,
    )
    db.commit()
    db.refresh(item)
    return {"message": "QC completed & Item created with Batch ID", "item_id": item.id, "batch_number": item.batch_number}


@router.post("/work-orders/{wo_id}/recall-qc")
def recall_work_order_for_qc(
    wo_id: int,
    req: ReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_api_auth),
):
    _require_roles(current_user, UserRole.qc_manager.value)
    if not req.reason or not req.reason.strip():
        raise HTTPException(status_code=400, detail="Recall reason is required.")
    wo = require_work_order_access(db, current_user, wo_id, for_update=True)
    if wo.status != WorkOrderStatus.completed:
        raise HTTPException(status_code=409, detail="Only a Completed Work Order can be recalled.")
    item = db.query(ProcurementItem).filter(
        ProcurementItem.work_order_id == wo.id, ProcurementItem.status != "Invalidated",
    ).with_for_update().first()
    if item and db.query(AssetCapitalization).filter(AssetCapitalization.procurement_item_id == item.id).first():
        raise HTTPException(status_code=409, detail="Installed Item cannot be recalled without an Asset recall.")
    wo.status = WorkOrderStatus.qc_pending
    wo.qc_notes = (wo.qc_notes or "") + f"\n[QC Recall] {req.reason.strip()}"
    if item:
        item.status = "Invalidated"
        item.invalidated_at = datetime.utcnow()
        from app.services.inventory_service import record_stock_movement
        record_stock_movement(
            db=db,
            product_id=item.product_id,
            warehouse_id=item.warehouse_id,
            movement_type="OUTWARD",
            quantity=1,
            reference_no=item.batch_number,
            notes=f"QC recall: {req.reason.strip()}",
            created_by_id=current_user.id,
            commit=False,
        )
    for report in wo.qc_reports:
        report.is_valid = False
    db.commit()
    return {"id": wo.id, "status": wo.status.value, "item_invalidated": bool(item)}


@router.post("/items/{item_id}/create-asset")
@idempotent("procurement.asset.create")
def create_asset_from_item(
    item_id: int,
    req: AssetFromItemRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_api_auth),
):
    _require_roles(current_user, UserRole.vendor_technician.value)
    item = require_procurement_item_access(db, current_user, item_id, for_update=True)
    _require_vendor_record(current_user, item.vendor_id)
    existing = db.query(AssetCapitalization).filter(AssetCapitalization.procurement_item_id == item.id).first()
    if existing:
        return {"message": "Asset already exists", "asset_id": existing.id, "ac_number": existing.ac_number}
    if item.status != "Ready":
        raise HTTPException(status_code=409, detail="Only a Ready Item can be deployed.")

    ac_num = f"AC-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
    asset = AssetCapitalization(
        ac_number=ac_num,
        user_id=current_user.id,
        outlet_id=item.outlet_id,
        product_id=item.product_id, warehouse_id=item.warehouse_id,
        company_profile_id=current_user.company_profile_id,
        item_name=item.item_name,
        item_code=item.batch_number,
        quantity=1,
        warehouse_name=item.warehouse.name if item.warehouse else None,
        vendor_id=item.vendor_id,
        procurement_item_id=item.id,
        notes=req.notes,
        image_url=req.image_url,
        deployed_at=datetime.utcnow(),
        asset_state="Installed",
        status=ACStatus.deployed,
        sync_status=ACSyncStatus.not_applicable,
    )
    db.add(asset)
    item.status = "Asset Capitalised"
    from app.services.inventory_service import record_stock_movement
    record_stock_movement(
        db=db,
        product_id=item.product_id,
        warehouse_id=item.warehouse_id,
        movement_type="OUTWARD",
        quantity=1,
        reference_no=item.batch_number,
        notes=f"Installed at outlet {item.outlet_id}",
        created_by_id=current_user.id,
        commit=False,
    )
    db.commit()
    db.refresh(asset)
    return {"message": "Asset created successfully from Item", "asset_id": asset.id, "ac_number": asset.ac_number}


@router.post("/assets/{asset_id}/maintenance-logs")
@idempotent("procurement.maintenance.create")
def create_maintenance_log(
    asset_id: int,
    req: MaintenanceLogRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_api_auth),
):
    _require_roles(current_user, UserRole.vendor_technician.value, UserRole.qc_manager.value)
    asset = require_asset_access(db, current_user, asset_id)
    _require_vendor_record(current_user, asset.vendor_id)

    log = AssetMaintenanceLog(
        asset_id=asset.id,
        created_by_id=current_user.id,
        notes=req.notes,
        issue_description=req.notes,
        status="In Progress", progress_percent=0, vendor_id=asset.vendor_id,
        photo_url=req.photo_url,
    )
    db.add(log)
    db.flush()
    urls = req.image_urls or ([req.photo_url] if req.photo_url else [])
    _attachments(db, "maintenance_log", log.id, "maintenance_image", urls, current_user.id)
    db.commit()
    db.refresh(log)
    return {"message": "Maintenance log submitted successfully", "log_id": log.id}


@router.post("/maintenance-logs/{log_id}/progress")
@idempotent("procurement.maintenance.progress")
def report_maintenance_progress(
    log_id: int,
    req: ProgressRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_api_auth),
):
    _require_roles(
        current_user, UserRole.vendor_technician.value,
        UserRole.vendor_admin.value, UserRole.qc_manager.value,
    )
    if req.progress_percent < 0 or req.progress_percent > 100:
        raise HTTPException(status_code=400, detail="Progress must be between 0 and 100.")
    log = require_maintenance_access(db, current_user, log_id, for_update=True)
    _require_vendor_record(current_user, log.vendor_id)
    if log.status == "Validated":
        raise HTTPException(status_code=409, detail="Validated maintenance cannot be changed.")
    if req.progress_percent < log.progress_percent:
        raise HTTPException(status_code=409, detail="Maintenance progress cannot decrease.")
    log.progress_percent = req.progress_percent
    log.status = "Completed" if req.progress_percent == 100 else "In Progress"
    if req.progress_percent == 100:
        log.completed_at = datetime.utcnow()
    progress = MaintenanceProgressLog(
        maintenance_log_id=log.id, progress_percent=req.progress_percent,
        remarks=req.remarks, reported_by_id=current_user.id,
    )
    db.add(progress)
    db.flush()
    _attachments(db, "maintenance_progress", progress.id, "progress_image", req.image_urls, current_user.id)
    db.commit()
    return {"id": log.id, "status": log.status, "progress_percent": log.progress_percent}


@router.post("/maintenance-logs/{log_id}/validate")
def validate_maintenance_completion(
    log_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_api_auth),
):
    _require_roles(current_user, UserRole.qc_manager.value)
    log = require_maintenance_access(db, current_user, log_id, for_update=True)
    _require_vendor_record(current_user, log.vendor_id)
    if log.status != "Completed" or log.progress_percent != 100:
        raise HTTPException(status_code=409, detail="Only completed maintenance can be validated.")
    log.status = "Validated"
    log.validated_by_id = current_user.id
    log.validated_at = datetime.utcnow()
    db.commit()
    return {"id": log.id, "status": log.status}


@router.get("/assets/{asset_id}/maintenance-logs")
def get_maintenance_logs(
    asset_id: int,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_api_auth),
):
    require_asset_access(db, current_user, asset_id)
    query = db.query(AssetMaintenanceLog).filter(AssetMaintenanceLog.asset_id == asset_id)
    total = query.count()
    logs = query.order_by(AssetMaintenanceLog.created_at.desc()).offset(
        (page - 1) * per_page
    ).limit(per_page).all()
    return {"page": page, "per_page": per_page, "total": total, "items": [
        {
            "id": l.id,
            "asset_id": l.asset_id,
            "created_by": l.created_by.full_name if l.created_by else "System",
            "notes": l.notes,
            "photo_url": l.photo_url,
            "created_at": l.created_at.isoformat(),
        }
        for l in logs
    ]}


@router.get("/work-orders")
def list_work_orders(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_api_auth),
):
    query = scope_work_order_query(
        db.query(WorkOrder).options(
            joinedload(WorkOrder.vendor),
            joinedload(WorkOrder.material_request).selectinload(MaterialRequest.recces),
        ),
        current_user,
        db,
    )
    total = query.count()
    orders = query.order_by(WorkOrder.created_at.desc()).offset(
        (page - 1) * per_page
    ).limit(per_page).all()
    return {
        "page": page, "per_page": per_page, "total": total,
        "items": [
            {
                "id": wo.id,
                "wo_number": wo.wo_number,
                "quotation_id": wo.quotation_id,
                "material_request_id": wo.material_request_id,
                "vendor_id": wo.vendor_id,
                "vendor_name": wo.vendor.name if wo.vendor else "Assigned Vendor",
                "status": wo.status.value,
                "progress_percent": wo.progress_percent,
                "manufactured_photo_url": wo.manufactured_photo_url,
                "notes": wo.notes,
                "recce": {
                    "dimensions": wo.material_request.recces[0].dimensions if wo.material_request and wo.material_request.recces else "10ft x 4ft",
                    "material_specifications": wo.material_request.recces[0].material_specifications if wo.material_request and wo.material_request.recces else "Acrylic 3mm LED",
                } if wo.material_request else None,
                "created_at": wo.created_at.isoformat(),
            }
            for wo in orders
        ]
    }


@router.get("/items")
def list_procurement_items(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_api_auth),
):
    query = scope_procurement_item_query(
        db.query(ProcurementItem).options(joinedload(ProcurementItem.outlet)),
        current_user,
        db,
    )
    total = query.count()
    items = query.order_by(ProcurementItem.created_at.desc()).offset(
        (page - 1) * per_page
    ).limit(per_page).all()
    return {
        "page": page, "per_page": per_page, "total": total,
        "items": [
            {
                "id": item.id,
                "work_order_id": item.work_order_id,
                "vendor_id": item.vendor_id,
                "outlet_id": item.outlet_id,
                "item_name": item.item_name,
                "batch_number": item.batch_number,
                "final_dimensions": item.final_dimensions,
                "final_specifications": item.final_specifications,
                "qc_notes": item.qc_notes,
                "status": item.status,
                "warehouse_id": item.warehouse_id,
                "outlet": {
                    "id": item.outlet.id, "name": item.outlet.name,
                    "gps_lat": item.outlet.gps_lat, "gps_lng": item.outlet.gps_lng,
                } if item.outlet else None,
                "created_at": item.created_at.isoformat(),
            }
            for item in items
        ]
    }


@router.get("/assets")
def list_procured_assets(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_api_auth),
):
    query = scope_asset_query(
        db.query(AssetCapitalization).options(joinedload(AssetCapitalization.outlet)),
        current_user,
        db,
    ).filter(AssetCapitalization.procurement_item_id.isnot(None))
    total = query.count()
    assets = query.order_by(AssetCapitalization.created_at.desc()).offset(
        (page - 1) * per_page
    ).limit(per_page).all()
    return {"page": page, "per_page": per_page, "total": total, "items": [{
        "id": asset.id, "ac_number": asset.ac_number, "asset_state": asset.asset_state,
        "item_name": asset.item_name, "item_code": asset.item_code,
        "outlet_name": asset.outlet.name if asset.outlet else None,
        "vendor_id": asset.vendor_id, "procurement_item_id": asset.procurement_item_id,
    } for asset in assets]}


@router.get("/maintenance-logs")
def list_maintenance_logs(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_api_auth),
):
    query = scope_maintenance_query(
        db.query(AssetMaintenanceLog), current_user, db
    )
    total = query.count()
    logs = query.order_by(AssetMaintenanceLog.created_at.desc()).offset(
        (page - 1) * per_page
    ).limit(per_page).all()
    return {"page": page, "per_page": per_page, "total": total, "items": [{
        "id": log.id, "asset_id": log.asset_id, "issue_description": log.issue_description or log.notes,
        "status": log.status, "progress_percent": log.progress_percent,
        "created_at": log.created_at.isoformat() if log.created_at else None,
    } for log in logs]}


@router.get("/vendors")
def list_vendors(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_api_auth),
):
    query = scope_vendor_query(db.query(Vendor), current_user, db)
    total = query.count()
    vendors = query.order_by(Vendor.name).offset(
        (page - 1) * per_page
    ).limit(per_page).all()
    return {
        "page": page, "per_page": per_page, "total": total,
        "items": [
            {
                "id": v.id,
                "name": v.name,
                "code": v.code,
                "contact_person": v.contact_person,
                "phone": v.phone,
            }
            for v in vendors
        ]
    }
