"""Asset capitalizations deployed through the native procurement workflow."""
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_web_auth, require_web_roles
from app.models.asset_capitalization import (
    ACStatus, ACSyncStatus, AssetCapitalization, DeployedByType,
)
from app.models.company import CompanyProfile
from app.models.outlet import Outlet, OutletStatus
from app.models.user import User, UserRole
from app.models.vendor import Vendor, VendorEmployee
from app.models.warehouse import Warehouse
from app.services.access_control import (
    build_access_scope,
    require_asset_access,
    require_outlet_access,
    require_vendor_access,
    scope_asset_query,
    scope_outlet_query,
)
from app.utils.flash import get_flash, set_flash_error, set_flash_success
from app.utils.geography_scope import get_user_allowed_warehouse_ids
from app.utils.pagination import paginate

router = APIRouter(prefix="/operations/marketing-assets", tags=["asset-capitalizations"])
templates = Jinja2Templates(directory="app/templates")


def _ac_number(db: Session) -> str:
    """Generate unique AC number."""
    from sqlalchemy import func
    count = db.query(func.count(AssetCapitalization.id)).scalar() or 0
    return f"AC-{count + 1:06d}"


@router.get("", response_class=HTMLResponse)
async def ac_list(
    request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
    status: str = Query(default=""),
    page: int = Query(default=1, ge=1),
):
    query = scope_asset_query(db.query(AssetCapitalization), current_user, db)
    if status and status in [s.value for s in ACStatus]:
        query = query.filter(AssetCapitalization.status == status)
    query = query.order_by(AssetCapitalization.created_at.desc())
    pagination = paginate(query, page)
    return templates.TemplateResponse("asset_capitalizations/list.html", {
        "request": request, "current_user": current_user,
        "pagination": pagination, "status": status,
        "ACStatus": ACStatus, **get_flash(request),
    })


@router.get("/new", response_class=HTMLResponse)
async def ac_new(
    request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
):
    outlets = scope_outlet_query(
        db.query(Outlet).filter(Outlet.status == OutletStatus.active),
        current_user,
        db,
    ).order_by(Outlet.name).all()
    access_scope = build_access_scope(current_user, db)
    vendor_query = db.query(Vendor).filter(Vendor.status == "active")
    if not access_scope.unrestricted:
        vendor_query = vendor_query.filter(
            Vendor.id.in_(access_scope.vendor_ids or {-1})
        )
    vendors = vendor_query.order_by(Vendor.name).all()
    allowed_wh_ids = get_user_allowed_warehouse_ids(current_user, db)
    wh_query = db.query(Warehouse).filter(Warehouse.is_active == True)
    if allowed_wh_ids is not None:
        wh_query = wh_query.filter(Warehouse.id.in_(allowed_wh_ids))
    warehouses = wh_query.order_by(Warehouse.name).all()
    return templates.TemplateResponse("asset_capitalizations/form.html", {
        "request": request, "current_user": current_user,
        "outlets": outlets, "vendors": vendors, "warehouses": warehouses,
        "DeployedByType": DeployedByType, "error": None,
    })


@router.post("/new")
async def ac_create(
    request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
    outlet_id: str = Form(...),
    item_name: str = Form(...),
    item_code: Optional[str] = Form(default=None),
    quantity: int = Form(default=1),
    warehouse_name: Optional[str] = Form(default=None),
    deployed_by: str = Form(default="rep"),
    vendor_id: Optional[str] = Form(default=None),
    notes: Optional[str] = Form(default=None),
    image: Optional[UploadFile] = File(default=None),
):
    outlet = require_outlet_access(db, current_user, int(outlet_id), active_only=True)
    selected_vendor_id = int(vendor_id) if vendor_id else None
    if selected_vendor_id:
        require_vendor_access(db, current_user, selected_vendor_id)

    ac_num = _ac_number(db)

    image_url = None
    if image and image.filename:
        file_bytes = await image.read()
        if file_bytes:
            from app.utils.s3_service import upload_image_file
            image_url = upload_image_file(
                db=db,
                file_bytes=file_bytes,
                original_filename=image.filename,
                folder_prefix="assets",
                content_type=image.content_type or "image/jpeg",
                bucket_type="permanent",
            )

    ac = AssetCapitalization(
        ac_number=ac_num,
        user_id=current_user.id,
        outlet_id=outlet.id,
        company_profile_id=current_user.company_profile_id,
        item_name=item_name,
        item_code=item_code or None,
        quantity=quantity,
        warehouse_name=warehouse_name or None,
        deployed_by=DeployedByType(deployed_by),
        vendor_id=selected_vendor_id,
        status=ACStatus.pending,
        sync_status=ACSyncStatus.pending,
        notes=notes or None,
        image_url=image_url,
    )
    db.add(ac)
    db.commit()

    from app.services.native_operations_service import deploy_asset_capitalization_natively
    deploy_asset_capitalization_natively(ac, db)

    set_flash_success(request, f"Asset capitalization {ac_num} created.")
    return RedirectResponse("/operations/marketing-assets", status_code=302)


@router.get("/{ac_id}", response_class=HTMLResponse)
async def ac_detail(
    ac_id: int, request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
):
    item = require_asset_access(db, current_user, ac_id)
    return templates.TemplateResponse("asset_capitalizations/detail.html", {
        "request": request, "current_user": current_user,
        "item": item, "ACStatus": ACStatus, "ACSyncStatus": ACSyncStatus,
        **get_flash(request),
    })

