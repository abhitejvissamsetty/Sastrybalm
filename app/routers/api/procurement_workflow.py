import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_api_auth
from app.models.asset_capitalization import AssetCapitalization, AssetMaintenanceLog
from app.models.material_request import MaterialRequest, MRStatus
from app.models.outlet import Outlet
from app.models.procurement import ProcurementItem, QuotationStatus, VendorQuotation, WorkOrder, WorkOrderStatus
from app.models.recce import RecceInformation
from app.models.user import User, UserRole
from app.models.vendor import Vendor

router = APIRouter(prefix="/api/v1/procurement", tags=["procurement-workflow"])

# ── Schemas ───────────────────────────────────────────────────────────────────

class RecceCreateRequest(BaseModel):
    dimensions: str
    material_specifications: Optional[str] = None
    client_notes: Optional[str] = None
    photo_url: Optional[str] = None

class QuotationCreateRequest(BaseModel):
    material_request_id: int
    recce_id: Optional[int] = None
    quote_amount: float
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
    batch_number: Optional[str] = None

class AssetFromItemRequest(BaseModel):
    notes: Optional[str] = None
    image_url: Optional[str] = None

class MaintenanceLogRequest(BaseModel):
    notes: str
    photo_url: Optional[str] = None

# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/material-requests/{mr_id}/assign-vendor")
def assign_vendor(
    mr_id: int,
    vendor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_api_auth),
):
    mr = db.query(MaterialRequest).filter(MaterialRequest.id == mr_id).first()
    if not mr:
        raise HTTPException(status_code=404, detail="Material Request not found")

    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    mr.vendor_id = vendor_id
    mr.status = MRStatus.vendor_assigned
    db.commit()
    db.refresh(mr)
    return {"message": "Vendor assigned successfully", "material_request_id": mr.id, "vendor_id": vendor_id, "status": mr.status.value}


@router.post("/material-requests/{mr_id}/recce")
def submit_recce(
    mr_id: int,
    req: RecceCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_api_auth),
):
    mr = db.query(MaterialRequest).filter(MaterialRequest.id == mr_id).first()
    if not mr:
        raise HTTPException(status_code=404, detail="Material Request not found")

    recce = RecceInformation(
        material_request_id=mr.id,
        vendor_id=mr.vendor_id or current_user.vendor_id or 1,
        created_by_id=current_user.id,
        dimensions=req.dimensions,
        material_specifications=req.material_specifications,
        client_notes=req.client_notes,
        photo_url=req.photo_url,
    )
    db.add(recce)
    mr.status = MRStatus.recce_completed
    db.commit()
    db.refresh(recce)
    return {"message": "Recce Information submitted successfully", "recce_id": recce.id, "mr_status": mr.status.value}


@router.get("/material-requests/{mr_id}/recce")
def get_recce(
    mr_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_api_auth),
):
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
def create_quotation(
    req: QuotationCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_api_auth),
):
    mr = db.query(MaterialRequest).filter(MaterialRequest.id == req.material_request_id).first()
    if not mr:
        raise HTTPException(status_code=404, detail="Material Request not found")

    vendor_id = current_user.vendor_id or mr.vendor_id or 1
    quote = VendorQuotation(
        material_request_id=mr.id,
        vendor_id=vendor_id,
        recce_id=req.recce_id,
        quote_amount=req.quote_amount,
        lead_time_days=req.lead_time_days,
        notes=req.notes,
        counter_recce_notes=req.counter_recce_notes,
        status=QuotationStatus.pending,
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
    quote = db.query(VendorQuotation).filter(VendorQuotation.id == quote_id).first()
    if not quote:
        raise HTTPException(status_code=404, detail="Quotation not found")

    quote.status = QuotationStatus.approved
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
        status=WorkOrderStatus.issued,
    )
    db.add(wo)
    db.commit()
    db.refresh(wo)
    return {"message": "Quotation approved & Work Order created successfully", "work_order_id": wo.id, "wo_number": wo.wo_number}


@router.post("/work-orders/{wo_id}/submit-qc")
def submit_work_order_qc(
    wo_id: int,
    req: WorkOrderQcSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_api_auth),
):
    wo = db.query(WorkOrder).filter(WorkOrder.id == wo_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="Work Order not found")

    wo.status = WorkOrderStatus.qc_pending
    if req.manufactured_photo_url:
        wo.manufactured_photo_url = req.manufactured_photo_url
    if req.notes:
        wo.notes = req.notes

    if wo.material_request:
        wo.material_request.status = MRStatus.qc_pending

    db.commit()
    db.refresh(wo)
    return {"message": "Work Order status updated to QC Pending", "work_order_id": wo.id, "status": wo.status.value}


@router.post("/work-orders/{wo_id}/qc-complete")
def complete_qc_work_order(
    wo_id: int,
    req: QcCompletionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_api_auth),
):
    wo = db.query(WorkOrder).filter(WorkOrder.id == wo_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="Work Order not found")

    wo.status = WorkOrderStatus.completed
    wo.qc_verified_by_id = current_user.id
    wo.qc_verified_at = datetime.utcnow()
    wo.qc_notes = req.qc_notes

    if wo.material_request:
        wo.material_request.status = MRStatus.completed

    # Allocate Batch Number & Create ProcurementItem
    batch_num = req.batch_number or f"BATCH-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
    mr = wo.material_request
    item_name = mr.category or mr.description[:30] if mr else "Procurement Item"
    
    item = ProcurementItem(
        work_order_id=wo.id,
        vendor_id=wo.vendor_id or 1,
        outlet_id=wo.outlet_id or (mr.outlet_id if mr else 1),
        item_name=item_name,
        batch_number=batch_num,
        final_dimensions=req.final_dimensions,
        final_specifications=req.final_specifications,
        qc_notes=req.qc_notes,
        qc_manager_id=current_user.id,
        status="pending_installation",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"message": "QC completed & Item created with Batch ID", "item_id": item.id, "batch_number": item.batch_number}


@router.post("/items/{item_id}/create-asset")
def create_asset_from_item(
    item_id: int,
    req: AssetFromItemRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_api_auth),
):
    item = db.query(ProcurementItem).filter(ProcurementItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Procurement Item not found")

    ac_num = f"AC-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
    asset = AssetCapitalization(
        ac_number=ac_num,
        user_id=current_user.id,
        outlet_id=item.outlet_id,
        item_name=item.item_name,
        item_code=item.batch_number,
        quantity=1,
        vendor_id=item.vendor_id,
        procurement_item_id=item.id,
        notes=req.notes,
        image_url=req.image_url,
        deployed_at=datetime.utcnow(),
    )
    db.add(asset)
    item.status = "installed"
    db.commit()
    db.refresh(asset)
    return {"message": "Asset created successfully from Item", "asset_id": asset.id, "ac_number": asset.ac_number}


@router.post("/assets/{asset_id}/maintenance-logs")
def create_maintenance_log(
    asset_id: int,
    req: MaintenanceLogRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_api_auth),
):
    asset = db.query(AssetCapitalization).filter(AssetCapitalization.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    log = AssetMaintenanceLog(
        asset_id=asset.id,
        created_by_id=current_user.id,
        notes=req.notes,
        photo_url=req.photo_url,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return {"message": "Maintenance log submitted successfully", "log_id": log.id}


@router.get("/assets/{asset_id}/maintenance-logs")
def get_maintenance_logs(
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_api_auth),
):
    logs = db.query(AssetMaintenanceLog).filter(AssetMaintenanceLog.asset_id == asset_id).order_by(AssetMaintenanceLog.created_at.desc()).all()
    return [
        {
            "id": l.id,
            "asset_id": l.asset_id,
            "created_by": l.created_by.full_name if l.created_by else "System",
            "notes": l.notes,
            "photo_url": l.photo_url,
            "created_at": l.created_at.isoformat(),
        }
        for l in logs
    ]


@router.get("/work-orders")
def list_work_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_api_auth),
):
    orders = db.query(WorkOrder).order_by(WorkOrder.created_at.desc()).all()
    return {
        "items": [
            {
                "id": wo.id,
                "wo_number": wo.wo_number,
                "quotation_id": wo.quotation_id,
                "material_request_id": wo.material_request_id,
                "vendor_id": wo.vendor_id,
                "vendor_name": wo.vendor.name if wo.vendor else "Assigned Vendor",
                "status": wo.status.value,
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
    db: Session = Depends(get_db),
    current_user: User = Depends(require_api_auth),
):
    items = db.query(ProcurementItem).order_by(ProcurementItem.created_at.desc()).all()
    return {
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
                "created_at": item.created_at.isoformat(),
            }
            for item in items
        ]
    }


@router.get("/vendors")
def list_vendors(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_api_auth),
):
    vendors = db.query(Vendor).all()
    return {
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
