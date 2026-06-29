import asyncio
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.adapters.cmms import cmms_adapter
from app.dependencies import get_db, require_web_auth, require_web_roles
from app.models.alert import Alert, AlertSeverity, AlertType
from app.models.material_request import MaterialRequest, MRStatus, MRSyncStatus
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
    if current_user.role.value in ["admin", "manager"]:
        reps = (
            db.query(User)
            .filter(User.role == UserRole.field_rep, User.is_active == True)
            .order_by(User.full_name)
            .all()
        )

    return templates.TemplateResponse("material_requests/list.html", {
        "request": request, "current_user": current_user,
        "pagination": pagination, "status": status, "user_id": user_id,
        "reps": reps, "MRStatus": MRStatus, "MRSyncStatus": MRSyncStatus,
        **get_flash(request),
    })


@router.get("/{mr_id}", response_class=HTMLResponse)
async def mr_detail(
    mr_id: int, request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
):
    q = db.query(MaterialRequest).filter(MaterialRequest.id == mr_id)
    if current_user.role == UserRole.field_rep:
        q = q.filter(MaterialRequest.user_id == current_user.id)
    item = q.first()
    if not item:
        set_flash_error(request, "Material request not found.")
        return RedirectResponse("/material-requests", status_code=302)
    return templates.TemplateResponse("material_requests/detail.html", {
        "request": request, "current_user": current_user,
        "item": item, "MRStatus": MRStatus, "MRSyncStatus": MRSyncStatus,
        **get_flash(request),
    })


@router.post("/{mr_id}/status")
async def mr_update_status(
    mr_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
    new_status: str = Query(default=""),
):
    from fastapi import Form
    form = await request.form()
    new_status = form.get("new_status", "")
    valid = [s.value for s in MRStatus]
    item = db.query(MaterialRequest).filter(MaterialRequest.id == mr_id).first()
    if not item:
        set_flash_error(request, "Material request not found.")
        return RedirectResponse("/material-requests", status_code=302)
    if new_status not in valid:
        set_flash_error(request, "Invalid status.")
        return RedirectResponse(f"/material-requests/{mr_id}", status_code=302)
    item.status = MRStatus(new_status)
    db.commit()
    set_flash_success(request, f"Status updated to {new_status}.")
    return RedirectResponse(f"/material-requests/{mr_id}", status_code=302)


@router.post("/{mr_id}/sync-cmms")
async def mr_sync_cmms(
    mr_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
):
    """Submit or re-submit a material request to CMMS."""
    item = db.query(MaterialRequest).filter(MaterialRequest.id == mr_id).first()
    if not item:
        set_flash_error(request, "Material request not found.")
        return RedirectResponse("/material-requests", status_code=302)

    if item.status not in (MRStatus.submitted, MRStatus.acknowledged):
        set_flash_error(request, "Only submitted or acknowledged requests can be synced to CMMS.")
        return RedirectResponse(f"/material-requests/{mr_id}", status_code=302)

    # Mark as pending sync
    item.sync_status = MRSyncStatus.pending
    item.sync_error = None
    db.commit()

    from datetime import timedelta
    from app.adapters.cmms import CMSAdapter
    from app.models.company import CompanyProfile
    from app.models.product import Product
    from app.models.product_mapping import ProductAliasMap, AccountAliasMap
    from app.utils.encryption import decrypt

    profile = db.query(CompanyProfile).filter(CompanyProfile.id == item.company_profile_id).first()
    if not profile or not profile.cmms_base_url:
        set_flash_error(request, "CMMS configuration missing for this company profile.")
        return RedirectResponse(f"/material-requests/{mr_id}", status_code=302)

    api_key_secret = decrypt(profile.cmms_api_key_encrypted)

    # 1. Resolve custom_location (Territory name or outlet name or "Test Location")
    custom_location = "Test Location"
    if item.outlet:
        if item.outlet.territory:
            custom_location = item.outlet.territory.name
        else:
            custom_location = item.outlet.name

    # 2. Resolve items.item_code dynamically
    cmms_item_code = "MBLIT"  # Default fallback
    if item.category:
        product = db.query(Product).filter(
            (Product.sku == item.category) | 
            (Product.erp_id == item.category) | 
            (Product.name == item.category)
        ).first()
        if product:
            alias = db.query(ProductAliasMap).filter(
                ProductAliasMap.company_profile_id == item.company_profile_id,
                ProductAliasMap.product_id == product.id
            ).first()
            if alias and alias.cmms_item_code:
                cmms_item_code = alias.cmms_item_code
            else:
                cmms_item_code = product.sku or product.erp_id or cmms_item_code
        else:
            cmms_item_code = item.category

    # 3. Resolve warehouse, expense_account, cost_center dynamically
    warehouse_alias = db.query(AccountAliasMap).filter(
        AccountAliasMap.company_profile_id == item.company_profile_id,
        AccountAliasMap.account_name == "warehouse"
    ).first()
    warehouse = warehouse_alias.cmms_account_code if warehouse_alias else f"Stores - {profile.code}"

    expense_alias = db.query(AccountAliasMap).filter(
        AccountAliasMap.company_profile_id == item.company_profile_id,
        AccountAliasMap.account_name == "expense_account"
    ).first()
    expense_account = expense_alias.cmms_account_code if expense_alias else f"Capital Equipment - {profile.code}"

    cost_center_alias = db.query(AccountAliasMap).filter(
        AccountAliasMap.company_profile_id == item.company_profile_id,
        AccountAliasMap.account_name == "cost_center"
    ).first()
    cost_center = cost_center_alias.cmms_account_code if cost_center_alias else f"Main - {profile.code}"

    # Build the items list
    schedule_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    items_payload = [
        {
            "item_code": cmms_item_code,
            "qty": 1,
            "custom_request_description": item.description,
            "schedule_date": schedule_date,
            "warehouse": warehouse,
            "uom": "Nos",
            "expense_account": expense_account,
            "cost_center": cost_center
        }
    ]

    # Build the CMMS/Frappe Material Request document payload
    payload = {
        "material_request_type": "Purchase",
        "company": profile.cmms_backend_company or profile.name,
        "custom_location": custom_location,
        "custom_raised_by": item.user.email if item.user else "N/A",
        "items": items_payload
    }

    dynamic_adapter = CMSAdapter(
        base_url=profile.cmms_base_url,
        api_key=api_key_secret
    )

    try:
        result = await dynamic_adapter.create_material_request(payload)
        item.sync_status = MRSyncStatus.synced
        item.cmms_ref = result.get("name") or result.get("id") or str(result)
        item.cmms_response = json.dumps(result)[:2000]
        item.sync_error = None
        item.sync_retries = 0
        db.commit()
        set_flash_success(request, f"Material request synced to CMMS. Ref: {item.cmms_ref}")
        logger.info("CMMS sync success — MR %s → ref %s", item.mr_number, item.cmms_ref)
    except Exception as exc:
        item.sync_status = MRSyncStatus.failed
        item.sync_error = str(exc)[:1000]
        item.sync_retries += 1
        db.add(Alert(
            severity=AlertSeverity.critical,
            alert_type=AlertType.sync_failure,
            title=f"CMMS sync failed: {item.mr_number}",
            message=f"Material request {item.mr_number} failed to sync to CMMS: {str(exc)[:500]}",
        ))
        db.commit()
        set_flash_error(request, f"CMMS sync failed: {exc}")
        logger.error("CMMS sync failed — MR %s: %s", item.mr_number, exc)

    return RedirectResponse(f"/material-requests/{mr_id}", status_code=302)
