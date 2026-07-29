import asyncio
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_web_roles, require_web_auth
from app.models.company import CompanyProfile, PaymentMode, SystemConfiguration
from app.models.user import User, UserRole
from app.utils.flash import get_flash, set_flash_error, set_flash_success
from app.utils.pagination import paginate

router = APIRouter(prefix="/company", tags=["company"])
templates = Jinja2Templates(directory="app/templates")


# ── GST Rate Extraction Helper ────────────────────────────────────────────────

import re as _re
from datetime import date as _date
from decimal import Decimal as _Decimal


def _extract_gst_from_taxes(taxes: list) -> "_Decimal":
    """Extract the effective GST rate from an ERPNext Item's `taxes` child table.

    ERPNext does NOT expose a flat `gst_rate` field.  Instead each Item carries a
    child table (`taxes`) where every row has:
      - `item_tax_template`: e.g. "GST 12% - SE-K"
      - `valid_from`:        e.g. "2025-09-21"

    Strategy:
      1. Keep only rows where valid_from ≤ today (or rows with no valid_from date).
      2. Among those, pick the row with the most-recent valid_from date.
      3. Parse the numeric percentage that appears immediately before the '%' in
         the template name (e.g. "GST 12% - SE-K" → 12).
    """
    if not taxes:
        return _Decimal("0")

    today = _date.today()
    valid_entries: list[tuple] = []
    for t in taxes:
        vf = t.get("valid_from")
        if not vf:
            valid_entries.append((_date.min, t))
        else:
            try:
                vf_date = _date.fromisoformat(str(vf)[:10])
                if vf_date <= today:
                    valid_entries.append((vf_date, t))
            except ValueError:
                valid_entries.append((_date.min, t))

    if not valid_entries:
        # All entries are future-dated; fall back to the first one
        valid_entries = [(_date.min, taxes[0])]

    # Most-recent valid entry first
    valid_entries.sort(key=lambda x: x[0], reverse=True)
    _, best = valid_entries[0]

    template = best.get("item_tax_template", "")
    match = _re.search(r"(\d+(?:\.\d+)?)\s*%", template)
    if match:
        return _Decimal(match.group(1))
    return _Decimal("0")


# ── Company Profiles ──────────────────────────────────────────────────────────

@router.get("/profiles", response_class=HTMLResponse)
async def profile_list(
    request: Request,
    page: int = Query(default=1, ge=1),
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    pagination = paginate(
        db.query(CompanyProfile).order_by(CompanyProfile.name), page
    )
    return templates.TemplateResponse("company/profile_list.html", {
        "request": request, "current_user": current_user,
        "profiles": pagination.items, "pagination": pagination, **get_flash(request),
    })


@router.get("/profiles/new", response_class=HTMLResponse)
async def profile_new(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
):
    return templates.TemplateResponse("company/profile_form.html", {
        "request": request, "current_user": current_user, "item": None, "error": None,
    })


@router.post("/profiles/new")
async def profile_create(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
    code: str = Form(...),
    name: str = Form(...),
):
    if db.query(CompanyProfile).filter(CompanyProfile.code == code.upper()).first():
        return templates.TemplateResponse("company/profile_form.html", {
            "request": request, "current_user": current_user, "item": None,
            "error": f"Code '{code.upper()}' already exists.",
        })
    profile = CompanyProfile(code=code.upper(), name=name)
    db.add(profile)
    db.commit()
    set_flash_success(request, f"Company profile '{name}' created.")
    return RedirectResponse("/company/profiles", status_code=302)


@router.get("/profiles/{profile_id}/edit", response_class=HTMLResponse)
async def profile_edit(
    profile_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    item = db.query(CompanyProfile).filter(CompanyProfile.id == profile_id).first()
    if not item or not item.is_active:
        set_flash_error(request, "Active profile not found or profile is inactive.")
        return RedirectResponse("/company/profiles", status_code=302)
    return templates.TemplateResponse("company/profile_form.html", {
        "request": request, "current_user": current_user, "item": item, "error": None,
    })


@router.post("/profiles/{profile_id}/edit")
async def profile_update(
    profile_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
    code: str = Form(...),
    name: str = Form(...),
):
    item = db.query(CompanyProfile).filter(CompanyProfile.id == profile_id).first()
    if not item or not item.is_active:
        set_flash_error(request, "Active profile not found or profile is inactive.")
        return RedirectResponse("/company/profiles", status_code=302)
    item.code = code.upper()
    item.name = name
    db.commit()
    set_flash_success(request, f"Company profile '{name}' updated.")
    return RedirectResponse("/company/profiles", status_code=302)


@router.post("/profiles/{profile_id}/activate")
async def profile_activate(
    profile_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    item = db.query(CompanyProfile).filter(CompanyProfile.id == profile_id).first()
    if item:
        item.is_active = True
        db.commit()
        set_flash_success(request, f"'{item.name}' activated.")
    return RedirectResponse("/company/profiles", status_code=302)


@router.post("/profiles/{profile_id}/delete")
async def profile_delete(
    profile_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    item = db.query(CompanyProfile).filter(CompanyProfile.id == profile_id).first()
    if item:
        has_active_users = db.query(User).filter(User.company_profile_id == profile_id, User.is_active == True).first()
        if has_active_users:
            set_flash_error(request, f"Cannot deactivate '{item.name}' because it has active assigned users.")
            return RedirectResponse("/company/profiles", status_code=302)
        
        item.is_active = False
        db.commit()
        set_flash_success(request, f"'{item.name}' deactivated.")
    return RedirectResponse("/company/profiles", status_code=302)


# ── System Configuration (singleton) ─────────────────────────────────────────

@router.get("/config", response_class=HTMLResponse)
async def system_config(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    config = db.query(SystemConfiguration).filter(SystemConfiguration.id == 1).first()
    return templates.TemplateResponse("company/config.html", {
        "request": request, "current_user": current_user,
        "config": config, **get_flash(request),
    })


@router.post("/company/config") # Note: target explicitly for absolute routing sanity
@router.post("/config")
async def system_config_update(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
    gps_threshold_metres: int = Form(default=100),
    sync_interval_seconds: int = Form(default=300),
    payment_mode: str = Form(default="cash_only"),
    denomination_mandatory: bool = Form(default=False),
    flag_gps_distance_metres: int = Form(default=100),
    flag_min_visit_seconds: int = Form(default=120),
):
    config = db.query(SystemConfiguration).filter(SystemConfiguration.id == 1).first()
    if not config:
        config = SystemConfiguration(id=1)
        db.add(config)
    config.gps_threshold_metres = max(10, gps_threshold_metres)
    config.sync_interval_seconds = max(60, sync_interval_seconds)
    config.flag_gps_distance_metres = max(10, flag_gps_distance_metres)
    config.flag_min_visit_seconds = max(10, flag_min_visit_seconds)
    
    from app.models.company import PaymentMode
    try:
        config.payment_mode = PaymentMode(payment_mode)
    except ValueError:
        config.payment_mode = PaymentMode.cash_only
    config.denomination_mandatory = denomination_mandatory
    
    db.commit()
    set_flash_success(request, "System configuration saved.")
    return RedirectResponse("/company/config", status_code=302)


# ── Product Mappings CRUD ──────────────────────────────────────────────────────

@router.get("/profiles/{profile_id}/product-mappings", response_class=HTMLResponse)
async def product_mappings_list(
    profile_id: int, request: Request,
    page: int = Query(default=1, ge=1),
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    if current_user.role != UserRole.admin and current_user.company_profile_id != profile_id:
        raise HTTPException(status_code=403, detail="Not authorized to access mappings for this company profile.")
    profile = db.query(CompanyProfile).filter(CompanyProfile.id == profile_id).first()
    if not profile or not profile.is_active:
        set_flash_error(request, "Active profile not found.")
        return RedirectResponse("/company/profiles", status_code=302)
        
    from app.models.product_mapping import ProductAliasMap
    from app.models.product import Product
    
    pagination = paginate(
        db.query(ProductAliasMap)
        .filter(ProductAliasMap.company_profile_id == profile_id)
        .order_by(ProductAliasMap.id),
        page,
    )
    mappings = pagination.items
    products = (
        db.query(Product).filter(Product.is_active == True)
        .order_by(Product.name).limit(500).all()
    )
    
    return templates.TemplateResponse("company/product_mappings.html", {
        "request": request, "current_user": current_user,
        "profile": profile, "mappings": mappings, "products": products,
        "pagination": pagination,
        **get_flash(request),
    })


@router.post("/profiles/{profile_id}/product-mappings/new")
async def product_mapping_create(
    profile_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
    product_id: int = Form(...),
    conversion_factor: float = Form(default=1.0),
):
    if current_user.role != UserRole.admin and current_user.company_profile_id != profile_id:
        raise HTTPException(status_code=403, detail="Not authorized to access mappings for this company profile.")
        
    profile = db.query(CompanyProfile).filter(CompanyProfile.id == profile_id).first()
    if not profile or not profile.is_active:
        set_flash_error(request, "Active profile not found.")
        return RedirectResponse("/company/profiles", status_code=302)
        
    from app.models.product_mapping import ProductAliasMap
    from decimal import Decimal
    
    exists = db.query(ProductAliasMap).filter(
        ProductAliasMap.company_profile_id == profile_id,
        ProductAliasMap.product_id == product_id
    ).first()
    if exists:
        set_flash_error(request, "A mapping for this product already exists.")
        return RedirectResponse(f"/company/profiles/{profile_id}/product-mappings", status_code=302)
        
    mapping = ProductAliasMap(
        company_profile_id=profile_id,
        product_id=product_id,
        conversion_factor=Decimal(str(conversion_factor)),
    )
    db.add(mapping)
    db.commit()
    set_flash_success(request, "Product mapping added.")
    return RedirectResponse(f"/company/profiles/{profile_id}/product-mappings", status_code=302)
 
 
@router.post("/profiles/{profile_id}/product-mappings/{mapping_id}/edit")
async def product_mapping_update(
    profile_id: int, mapping_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
    conversion_factor: float = Form(default=1.0),
):
    if current_user.role != UserRole.admin and current_user.company_profile_id != profile_id:
        raise HTTPException(status_code=403, detail="Not authorized to access mappings for this company profile.")
        
    from app.models.product_mapping import ProductAliasMap
    from decimal import Decimal
    mapping = db.query(ProductAliasMap).filter(ProductAliasMap.id == mapping_id, ProductAliasMap.company_profile_id == profile_id).first()
    if mapping:
        mapping.conversion_factor = Decimal(str(conversion_factor))
        db.commit()
        set_flash_success(request, "Product mapping updated.")
    return RedirectResponse(f"/company/profiles/{profile_id}/product-mappings", status_code=302)


@router.post("/profiles/{profile_id}/product-mappings/{mapping_id}/delete")
async def product_mapping_delete(
    profile_id: int, mapping_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    if current_user.role != UserRole.admin and current_user.company_profile_id != profile_id:
        raise HTTPException(status_code=403, detail="Not authorized to access mappings for this company profile.")
        
    from app.models.product_mapping import ProductAliasMap
    mapping = db.query(ProductAliasMap).filter(ProductAliasMap.id == mapping_id, ProductAliasMap.company_profile_id == profile_id).first()
    if mapping:
        db.delete(mapping)
        db.commit()
        set_flash_success(request, "Product mapping removed.")
    return RedirectResponse(f"/company/profiles/{profile_id}/product-mappings", status_code=302)


# ── Account Mappings CRUD ──────────────────────────────────────────────────────

@router.get("/profiles/{profile_id}/account-mappings", response_class=HTMLResponse)
async def account_mappings_list(
    profile_id: int, request: Request,
    page: int = Query(default=1, ge=1),
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    if current_user.role != UserRole.admin and current_user.company_profile_id != profile_id:
        raise HTTPException(status_code=403, detail="Not authorized to access mappings for this company profile.")
    profile = db.query(CompanyProfile).filter(CompanyProfile.id == profile_id).first()
    if not profile or not profile.is_active:
        set_flash_error(request, "Active profile not found.")
        return RedirectResponse("/company/profiles", status_code=302)
        
    from app.models.product_mapping import AccountAliasMap
    
    pagination = paginate(
        db.query(AccountAliasMap)
        .filter(AccountAliasMap.company_profile_id == profile_id)
        .order_by(AccountAliasMap.id),
        page,
    )
    mappings = pagination.items
    
    return templates.TemplateResponse("company/account_mappings.html", {
        "request": request, "current_user": current_user,
        "profile": profile, "mappings": mappings, "pagination": pagination,
        **get_flash(request),
    })


@router.post("/profiles/{profile_id}/account-mappings/new")
async def account_mapping_create(
    profile_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
    account_name: str = Form(...),
    account_type: Optional[str] = Form(default=None),
):
    if current_user.role != UserRole.admin and current_user.company_profile_id != profile_id:
        raise HTTPException(status_code=403, detail="Not authorized to access mappings for this company profile.")
        
    profile = db.query(CompanyProfile).filter(CompanyProfile.id == profile_id).first()
    if not profile or not profile.is_active:
        set_flash_error(request, "Active profile not found.")
        return RedirectResponse("/company/profiles", status_code=302)
        
    from app.models.product_mapping import AccountAliasMap
    
    mapping = AccountAliasMap(
        company_profile_id=profile_id,
        account_name=account_name,
        account_type=account_type or None,
    )
    db.add(mapping)
    db.commit()
    set_flash_success(request, "Account mapping added.")
    return RedirectResponse(f"/company/profiles/{profile_id}/account-mappings", status_code=302)


@router.post("/profiles/{profile_id}/account-mappings/{mapping_id}/edit")
async def account_mapping_update(
    profile_id: int, mapping_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
    account_name: str = Form(...),
    account_type: Optional[str] = Form(default=None),
):
    if current_user.role != UserRole.admin and current_user.company_profile_id != profile_id:
        raise HTTPException(status_code=403, detail="Not authorized to access mappings for this company profile.")
        
    from app.models.product_mapping import AccountAliasMap
    mapping = db.query(AccountAliasMap).filter(AccountAliasMap.id == mapping_id, AccountAliasMap.company_profile_id == profile_id).first()
    if mapping:
        mapping.account_name = account_name
        mapping.account_type = account_type or None
        db.commit()
        set_flash_success(request, "Account mapping updated.")
    return RedirectResponse(f"/company/profiles/{profile_id}/account-mappings", status_code=302)


@router.post("/profiles/{profile_id}/account-mappings/{mapping_id}/delete")
async def account_mapping_delete(
    profile_id: int, mapping_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    if current_user.role != UserRole.admin and current_user.company_profile_id != profile_id:
        raise HTTPException(status_code=403, detail="Not authorized to access mappings for this company profile.")
        
    from app.models.product_mapping import AccountAliasMap
    mapping = db.query(AccountAliasMap).filter(AccountAliasMap.id == mapping_id, AccountAliasMap.company_profile_id == profile_id).first()
    if mapping:
        db.delete(mapping)
        db.commit()
        set_flash_success(request, "Account mapping removed.")
    return RedirectResponse(f"/company/profiles/{profile_id}/account-mappings", status_code=302)
