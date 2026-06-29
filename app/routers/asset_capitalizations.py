"""
Asset Capitalizations router — Rep or vendor technician deploys CMMS items at outlets.
No approval needed — goes direct to CMMS queue.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
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
from app.utils.flash import get_flash, set_flash_error, set_flash_success
from app.utils.pagination import paginate

router = APIRouter(prefix="/asset-capitalizations", tags=["asset-capitalizations"])
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
    query = db.query(AssetCapitalization)
    if current_user.role == UserRole.field_rep:
        query = query.filter(AssetCapitalization.user_id == current_user.id)
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
    outlets = db.query(Outlet).filter(Outlet.status == OutletStatus.active).order_by(Outlet.name).all()
    vendors = db.query(Vendor).filter(Vendor.status == "active").order_by(Vendor.name).all()
    return templates.TemplateResponse("asset_capitalizations/form.html", {
        "request": request, "current_user": current_user,
        "outlets": outlets, "vendors": vendors,
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
):
    ac_num = _ac_number(db)
    ac = AssetCapitalization(
        ac_number=ac_num,
        user_id=current_user.id,
        outlet_id=int(outlet_id),
        company_profile_id=current_user.company_profile_id,
        item_name=item_name,
        item_code=item_code or None,
        quantity=quantity,
        warehouse_name=warehouse_name or None,
        deployed_by=DeployedByType(deployed_by),
        vendor_id=int(vendor_id) if vendor_id else None,
        status=ACStatus.pending,
        sync_status=ACSyncStatus.pending,
        notes=notes or None,
    )
    db.add(ac)
    db.commit()

    # Queue CMMS sync
    await _sync_ac_to_cmms(ac, db)

    set_flash_success(request, f"Asset capitalization {ac_num} created.")
    return RedirectResponse("/asset-capitalizations", status_code=302)


@router.get("/{ac_id}", response_class=HTMLResponse)
async def ac_detail(
    ac_id: int, request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
):
    item = db.query(AssetCapitalization).filter(AssetCapitalization.id == ac_id).first()
    if not item:
        set_flash_error(request, "Asset capitalization not found.")
        return RedirectResponse("/asset-capitalizations", status_code=302)
    return templates.TemplateResponse("asset_capitalizations/detail.html", {
        "request": request, "current_user": current_user,
        "item": item, "ACStatus": ACStatus, "ACSyncStatus": ACSyncStatus,
        **get_flash(request),
    })


@router.post("/{ac_id}/sync-cmms")
async def ac_sync_cmms(
    ac_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
):
    item = db.query(AssetCapitalization).filter(AssetCapitalization.id == ac_id).first()
    if not item:
        set_flash_error(request, "Not found.")
        return RedirectResponse("/asset-capitalizations", status_code=302)
    item.sync_status = ACSyncStatus.pending
    item.sync_error = None
    db.commit()
    await _sync_ac_to_cmms(item, db)
    return RedirectResponse(f"/asset-capitalizations/{ac_id}", status_code=302)


async def _sync_ac_to_cmms(ac: AssetCapitalization, db: Session):
    """Internal helper: push asset capitalization to CMMS."""
    import logging
    from datetime import datetime
    from app.adapters.cmms import CMSAdapter
    from app.models.company import CompanyProfile
    from app.models.product import Product
    from app.models.product_mapping import ProductAliasMap, AccountAliasMap
    from app.utils.encryption import decrypt
    from app.models.alert import Alert, AlertSeverity, AlertType

    logger = logging.getLogger(__name__)

    profile = db.query(CompanyProfile).filter(CompanyProfile.id == ac.company_profile_id).first()
    if not profile or not profile.cmms_base_url:
        ac.sync_status = ACSyncStatus.failed
        ac.sync_error = "CMMS configuration missing for this company profile."
        ac.sync_retries += 1
        db.commit()
        return

    api_key_secret = decrypt(profile.cmms_api_key_encrypted)

    # 1. Resolve target_item_code
    target_item_code = "MBLIT"
    if ac.item_code:
        target_item_code = ac.item_code
    elif ac.item_name:
        product = db.query(Product).filter(
            (Product.sku == ac.item_name) | 
            (Product.erp_id == ac.item_name) | 
            (Product.name == ac.item_name)
        ).first()
        if product:
            alias = db.query(ProductAliasMap).filter(
                ProductAliasMap.company_profile_id == ac.company_profile_id,
                ProductAliasMap.product_id == product.id
            ).first()
            if alias and alias.cmms_item_code:
                target_item_code = alias.cmms_item_code
            else:
                target_item_code = product.sku or product.erp_id or target_item_code
        else:
            target_item_code = ac.item_name

    # 2. Resolve target_asset_location
    target_asset_location = "Test Location"
    if ac.outlet:
        if ac.outlet.territory:
            target_asset_location = ac.outlet.territory.name
        else:
            target_asset_location = ac.outlet.name

    # 3. Resolve service items & accounts
    service_item_code = "Installation Service"
    svc_prod = db.query(Product).filter(
        (Product.name == "Installation Service") | 
        (Product.erp_id == "Installation Service")
    ).first()
    if svc_prod:
        alias = db.query(ProductAliasMap).filter(
            ProductAliasMap.company_profile_id == ac.company_profile_id,
            ProductAliasMap.product_id == svc_prod.id
        ).first()
        if alias and alias.cmms_item_code:
            service_item_code = alias.cmms_item_code

    expense_alias = db.query(AccountAliasMap).filter(
        AccountAliasMap.company_profile_id == ac.company_profile_id,
        AccountAliasMap.account_name == "expense_account"
    ).first()
    expense_account = expense_alias.cmms_account_code if expense_alias else f"Capital Equipment - {profile.code}"

    cost_center_alias = db.query(AccountAliasMap).filter(
        AccountAliasMap.company_profile_id == ac.company_profile_id,
        AccountAliasMap.account_name == "cost_center"
    ).first()
    cost_center = cost_center_alias.cmms_account_code if cost_center_alias else f"Main - {profile.code}"

    service_items = [
        {
            "item_code": service_item_code,
            "qty": 1,
            "uom": "Nos",
            "rate": 100.0,
            "expense_account": expense_account,
            "cost_center": cost_center
        }
    ]

    posting_date = (ac.deployed_at or datetime.now()).strftime("%Y-%m-%d")

    # Build the CMMS/Frappe Asset Capitalization payload
    payload = {
        "company": profile.cmms_backend_company or profile.name,
        "target_item_code": target_item_code,
        "target_asset_location": target_asset_location,
        "posting_date": posting_date,
        "service_items": service_items,
        "custom_installation_notes": ac.notes or "Asset deployed by Sastrybalm rep",
        "custom_installation_photo_1": "",
        "custom_installation_length": 8,
        "custom_installation_height": 5,
        "custom_installation_depth": 0.8
    }

    dynamic_adapter = CMSAdapter(
        base_url=profile.cmms_base_url,
        api_key=api_key_secret
    )

    try:
        result = await dynamic_adapter.create_asset_capitalization(payload)
        ac.sync_status = ACSyncStatus.synced
        ac.cmms_ref = result.get("name") or result.get("id") or str(result)[:100]
        ac.sync_error = None
        ac.sync_retries = 0
        db.commit()
        logger.info("CMMS AC sync success — %s → %s", ac.ac_number, ac.cmms_ref)
    except Exception as exc:
        ac.sync_status = ACSyncStatus.failed
        ac.sync_error = str(exc)[:1000]
        ac.sync_retries += 1
        db.add(Alert(
            severity=AlertSeverity.critical,
            alert_type=AlertType.sync_failure,
            title=f"CMMS AC sync failed: {ac.ac_number}",
            message=str(exc)[:500],
        ))
        db.commit()
        logger.error("CMMS AC sync failed — %s: %s", ac.ac_number, exc)
