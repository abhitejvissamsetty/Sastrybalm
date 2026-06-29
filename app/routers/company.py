import asyncio
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_web_roles, require_web_auth
from app.models.company import CompanyProfile, PaymentMode, SystemConfiguration
from app.models.user import User, UserRole
from app.utils.encryption import decrypt, encrypt
from app.utils.flash import get_flash, set_flash_error, set_flash_success

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
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    profiles = db.query(CompanyProfile).order_by(CompanyProfile.name).all()
    return templates.TemplateResponse("company/profile_list.html", {
        "request": request, "current_user": current_user,
        "profiles": profiles, **get_flash(request),
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
    zap_base_url: Optional[str] = Form(default=None),
    zap_api_key: Optional[str] = Form(default=None),
    zap_backend_company: Optional[str] = Form(default=None),
    cmms_base_url: Optional[str] = Form(default=None),
    cmms_api_key: Optional[str] = Form(default=None),
    cmms_backend_company: Optional[str] = Form(default=None),
    connect_base_url: Optional[str] = Form(default=None),
    connect_api_key: Optional[str] = Form(default=None),
    connect_backend_company: Optional[str] = Form(default=None),
):
    if db.query(CompanyProfile).filter(CompanyProfile.code == code.upper()).first():
        return templates.TemplateResponse("company/profile_form.html", {
            "request": request, "current_user": current_user, "item": None,
            "error": f"Code '{code.upper()}' already exists.",
        })
    profile = CompanyProfile(
        code=code.upper(), name=name,
        zap_base_url=zap_base_url or None,
        zap_api_key_encrypted=encrypt(zap_api_key) if zap_api_key else None,
        zap_backend_company=zap_backend_company or None,
        cmms_base_url=cmms_base_url or None,
        cmms_api_key_encrypted=encrypt(cmms_api_key) if cmms_api_key else None,
        cmms_backend_company=cmms_backend_company or None,
        connect_base_url=connect_base_url or None,
        connect_api_key_encrypted=encrypt(connect_api_key) if connect_api_key else None,
        connect_backend_company=connect_backend_company or None,
    )
    # Add ZAP-READY tag if ZAP credentials are set
    tags = []
    if zap_base_url and zap_api_key:
        tags.append("ZAP-READY")
    if cmms_base_url and cmms_api_key:
        tags.append("CMMS-READY")
    if connect_base_url and connect_api_key:
        tags.append("CONNECT-READY")
    profile.set_tags(tags)
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
        "zap_api_key_hint": "••••••••" if item.zap_api_key_encrypted else "",
        "cmms_api_key_hint": "••••••••" if item.cmms_api_key_encrypted else "",
        "connect_api_key_hint": "••••••••" if item.connect_api_key_encrypted else "",
    })


@router.post("/profiles/{profile_id}/edit")
async def profile_update(
    profile_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
    code: str = Form(...),
    name: str = Form(...),
    zap_base_url: Optional[str] = Form(default=None),
    zap_api_key: Optional[str] = Form(default=None),
    zap_backend_company: Optional[str] = Form(default=None),
    cmms_base_url: Optional[str] = Form(default=None),
    cmms_api_key: Optional[str] = Form(default=None),
    cmms_backend_company: Optional[str] = Form(default=None),
    connect_base_url: Optional[str] = Form(default=None),
    connect_api_key: Optional[str] = Form(default=None),
    connect_backend_company: Optional[str] = Form(default=None),
):
    item = db.query(CompanyProfile).filter(CompanyProfile.id == profile_id).first()
    if not item or not item.is_active:
        set_flash_error(request, "Active profile not found or profile is inactive.")
        return RedirectResponse("/company/profiles", status_code=302)
    item.code = code.upper()
    item.name = name
    item.zap_base_url = zap_base_url or None
    item.zap_backend_company = zap_backend_company or None
    item.cmms_base_url = cmms_base_url or None
    item.cmms_backend_company = cmms_backend_company or None
    item.connect_base_url = connect_base_url or None
    item.connect_backend_company = connect_backend_company or None
    
    if zap_api_key:
        item.zap_api_key_encrypted = encrypt(zap_api_key)
    if cmms_api_key:
        item.cmms_api_key_encrypted = encrypt(cmms_api_key)
    if connect_api_key:
        item.connect_api_key_encrypted = encrypt(connect_api_key)

    # Maintain Dynamic Tags based on configured credentials
    tags = item.get_tags()
    if item.zap_base_url and item.zap_api_key_encrypted:
        if "ZAP-READY" not in tags and "ZAP-ERROR" not in tags:
            tags.append("ZAP-READY")
    else:
        if "ZAP-READY" in tags: tags.remove("ZAP-READY")
        if "ZAP-ERROR" in tags: tags.remove("ZAP-ERROR")

    if item.cmms_base_url and item.cmms_api_key_encrypted:
        if "CMMS-READY" not in tags and "CMMS-ERROR" not in tags:
            tags.append("CMMS-READY")
    else:
        if "CMMS-READY" in tags: tags.remove("CMMS-READY")
        if "CMMS-ERROR" in tags: tags.remove("CMMS-ERROR")

    if item.connect_base_url and item.connect_api_key_encrypted:
        if "CONNECT-READY" not in tags and "CONNECT-ERROR" not in tags:
            tags.append("CONNECT-READY")
    else:
        if "CONNECT-READY" in tags: tags.remove("CONNECT-READY")
        if "CONNECT-ERROR" in tags: tags.remove("CONNECT-ERROR")

    item.set_tags(tags)
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


@router.post("/profiles/{profile_id}/test-zap")
async def profile_test_zap(
    profile_id: int,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    from app.adapters.zap import ZapAdapter
    item = db.query(CompanyProfile).filter(CompanyProfile.id == profile_id).first()
    if not item or not item.zap_base_url or not item.zap_api_key_encrypted:
        return {"connected": False, "error": "ZAP Integration credentials not configured."}
    
    try:
        zap = ZapAdapter(
            base_url=item.zap_base_url,
            api_key=decrypt(item.zap_api_key_encrypted),
        )
        is_connected = await zap.test_connection()
        if not is_connected:
            item.add_tag("ZAP-ERROR")
            item.remove_tag("ZAP-READY")
            db.commit()
            return {"connected": False, "error": "Failed to authenticate with ZAP server."}
        
        company_filter = item.zap_backend_company or item.name
        products = await zap.fetch_products(company_filter)
        
        fallback_used = False
        if not products and company_filter:
            products = await zap.fetch_products(None)
            fallback_used = True
            
        from app.models.product import Product
        import logging
        logger = logging.getLogger(__name__)
        
        fetched_erp_ids = [p.get("name") for p in products if p.get("name")]
        
        db.query(Product).filter((Product.company_profile_id == item.id) & Product.erp_id.like("PROD-%")).update({"is_active": False}, synchronize_session=False)
        if fetched_erp_ids:
            db.query(Product).filter(
                (Product.company_profile_id == item.id) & 
                (Product.primary_category == "Products") &
                (~Product.erp_id.in_(fetched_erp_ids))
            ).update({"is_active": False}, synchronize_session=False)
        
        # Fetch full product details concurrently to extract GST rates from taxes child table
        erp_ids = [p.get("name") for p in products if p.get("name")]
        details = await asyncio.gather(*[zap.fetch_product_detail(eid) for eid in erp_ids], return_exceptions=True)
        details_map = {}
        for eid, detail in zip(erp_ids, details):
            if isinstance(detail, Exception) or not detail:
                details_map[eid] = {}
            else:
                details_map[eid] = detail

        for p in products:
            taxes_list = details_map.get(p.get("name"), {}).get("taxes", [])
            p["gst_rate"] = _extract_gst_from_taxes(taxes_list)

        upserted_count = 0
        from decimal import Decimal
        for p in products:
            erp_id = p.get("name")
            if not erp_id:
                continue
            name = p.get("item_name") or erp_id
            mrp_val = Decimal(str(p.get("item_mrp") or p.get("standard_rate") or p.get("last_purchase_rate") or 0))
            category_val = p.get("item_group") or "Products"
            sku_val = p.get("item_code") or erp_id
            
            existing_product = db.query(Product).filter(Product.erp_id == erp_id).first()
            if existing_product:
                existing_product.name = name
                existing_product.company_profile_id = item.id
                existing_product.is_active = True
                existing_product.mrp = mrp_val
                existing_product.gst_rate = Decimal(str(p.get("gst_rate") or 0))
                existing_product.primary_category = category_val
                existing_product.sku = sku_val
            else:
                db.add(Product(
                    erp_id=erp_id,
                    name=name,
                    company_profile_id=item.id,
                    is_active=True,
                    mrp=mrp_val,
                    gst_rate=Decimal(str(p.get("gst_rate") or 0)),
                    primary_category=category_val,
                    sku=sku_val,
                ))
            upserted_count += 1
            
        if upserted_count > 0 or fetched_erp_ids:
            db.commit()
            logger.info("ZAP: Successfully upserted %d products.", upserted_count)
            
        # Success Tagging
        item.add_tag("ZAP-READY")
        item.remove_tag("ZAP-ERROR")
        db.commit()

        message = "Connection test successful! Sastrybalm is communicating with the ZAP system."
        if fallback_used and upserted_count > 0:
            message += f" (Note: Synced {upserted_count} products using fallback fetch without company filter)."
        elif upserted_count > 0:
            message += f" (Note: Synced {upserted_count} products using company filter '{company_filter}')."
            
        return {
            "connected": True,
            "message": message,
            "company_name": item.name,
            "backend_company": item.zap_backend_company,
            "products_found": len(products),
            "sample_products": products[:5],
        }
    except Exception as exc:
        item.add_tag("ZAP-ERROR")
        item.remove_tag("ZAP-READY")
        db.commit()
        return {"connected": False, "error": f"Connection failed with error: {str(exc)}"}


@router.post("/profiles/{profile_id}/test-cmms")
async def profile_test_cmms(
    profile_id: int,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    from app.adapters.cmms import CMSAdapter
    import json
    import logging
    logger = logging.getLogger(__name__)
    item = db.query(CompanyProfile).filter(CompanyProfile.id == profile_id).first()
    if not item or not item.cmms_base_url or not item.cmms_api_key_encrypted:
        return {"connected": False, "error": "CMMS Integration credentials not configured."}
    
    try:
        cmms = CMSAdapter(
            base_url=item.cmms_base_url,
            api_key=decrypt(item.cmms_api_key_encrypted),
        )
        is_connected = await cmms.test_connection()
        if not is_connected:
            item.add_tag("CMMS-ERROR")
            item.remove_tag("CMMS-READY")
            db.commit()
            return {"connected": False, "error": "Failed to ping CMMS server."}
        
        company_filter = item.cmms_backend_company or item.name
        
        # Define the three base filters for Consumable items
        filters_1 = [["item_group", "=", "Consumable"], ["is_fixed_asset", "=", 1], ["is_stock_item", "=", 0], ["disabled", "=", 0]]
        filters_2 = [["item_group", "=", "Consumable"], ["is_fixed_asset", "=", 0], ["is_stock_item", "=", 1], ["disabled", "=", 0]]
        filters_3 = [["item_group", "=", "Consumable"], ["is_fixed_asset", "=", 0], ["is_stock_item", "=", 0], ["disabled", "=", 0]]
        
        async def fetch_type(filters_list):
            import copy
            f = copy.deepcopy(filters_list)
            if company_filter:
                f.append(["Item Default", "company", "=", company_filter])
            params = {
                "fields": json.dumps(["name", "item_name", "item_code", "item_group", "standard_rate"]),
                "limit_page_length": 0,
                "filters": json.dumps(f)
            }
            try:
                res = await cmms._request_with_retry("GET", "/api/resource/Item", params=params)
                data = res.get("data", [])
                if not data and company_filter:
                    f_fallback = copy.deepcopy(filters_list)
                    params["filters"] = json.dumps(f_fallback)
                    res = await cmms._request_with_retry("GET", "/api/resource/Item", params=params)
                    return res.get("data", [])
                return data
            except Exception:
                f_fallback = copy.deepcopy(filters_list)
                params["filters"] = json.dumps(f_fallback)
                try:
                    res = await cmms._request_with_retry("GET", "/api/resource/Item", params=params)
                    return res.get("data", [])
                except Exception:
                    return []
                
        products_1 = await fetch_type(filters_1)
        products_2 = await fetch_type(filters_2)
        products_3 = await fetch_type(filters_3)
        
        merged_products = {}
        for p in (products_1 + products_2 + products_3):
            code = p.get("name")
            if code:
                merged_products[code] = p
        products = list(merged_products.values())
        fallback_used = False

        from app.models.product import Product
        fetched_erp_ids = [p.get("name") for p in products if p.get("name")]
        
        db.query(Product).filter((Product.company_profile_id == item.id) & Product.erp_id.like("PROD-%")).update({"is_active": False}, synchronize_session=False)
        if fetched_erp_ids:
            db.query(Product).filter(
                (Product.company_profile_id == item.id) & 
                (Product.primary_category == "Consumable") &
                (~Product.erp_id.in_(fetched_erp_ids))
            ).update({"is_active": False}, synchronize_session=False)
        
        # Fetch full product details concurrently to extract GST rates from taxes child table
        erp_ids = [p.get("name") for p in products if p.get("name")]
        details = await asyncio.gather(*[cmms.fetch_product_detail(eid) for eid in erp_ids], return_exceptions=True)
        details_map = {}
        for eid, detail in zip(erp_ids, details):
            if isinstance(detail, Exception) or not detail:
                details_map[eid] = {}
            else:
                details_map[eid] = detail

        for p in products:
            taxes_list = details_map.get(p.get("name"), {}).get("taxes", [])
            p["gst_rate"] = _extract_gst_from_taxes(taxes_list)

        upserted_count = 0
        from decimal import Decimal
        for p in products:
            erp_id = p.get("name")
            if not erp_id:
                continue
            name = p.get("item_name") or erp_id
            mrp_val = Decimal(str(p.get("item_mrp") or p.get("standard_rate") or p.get("last_purchase_rate") or 0))
            category_val = p.get("item_group") or "Consumable"
            sku_val = p.get("item_code") or erp_id
            
            existing_product = db.query(Product).filter(Product.erp_id == erp_id).first()
            if existing_product:
                existing_product.name = name
                existing_product.company_profile_id = item.id
                existing_product.is_active = True
                existing_product.mrp = mrp_val
                existing_product.gst_rate = Decimal(str(p.get("gst_rate") or 0))
                existing_product.primary_category = category_val
                existing_product.sku = sku_val
            else:
                db.add(Product(
                    erp_id=erp_id,
                    name=name,
                    company_profile_id=item.id,
                    is_active=True,
                    mrp=mrp_val,
                    gst_rate=Decimal(str(p.get("gst_rate") or 0)),
                    primary_category=category_val,
                    sku=sku_val,
                ))
            upserted_count += 1
            
        if upserted_count > 0 or fetched_erp_ids:
            db.commit()
            logger.info("CMMS: Successfully upserted %d products.", upserted_count)

        # Success Tagging
        item.add_tag("CMMS-READY")
        item.remove_tag("CMMS-ERROR")
        db.commit()

        message = "Connection test successful! Sastrybalm is communicating with the CMMS platform."
        if fallback_used and upserted_count > 0:
            message += f" (Note: Synced {upserted_count} products using fallback fetch)."
        elif upserted_count > 0:
            message += f" (Note: Synced {upserted_count} products using company filter '{company_filter}')."

        return {
            "connected": True,
            "message": message,
            "company_name": item.name,
            "backend_company": item.cmms_backend_company,
            "products_found": len(products),
        }
    except Exception as exc:
        item.add_tag("CMMS-ERROR")
        item.remove_tag("CMMS-READY")
        db.commit()
        return {"connected": False, "error": f"Connection failed with error: {str(exc)}"}


@router.post("/profiles/{profile_id}/test-connect")
async def profile_test_connect(
    profile_id: int,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    from app.adapters.connect import ConnectAdapter
    import logging
    logger = logging.getLogger(__name__)
    item = db.query(CompanyProfile).filter(CompanyProfile.id == profile_id).first()
    if not item or not item.connect_base_url or not item.connect_api_key_encrypted:
        return {"connected": False, "error": "CONNECT Integration credentials not configured."}
    
    try:
        connect = ConnectAdapter(
            base_url=item.connect_base_url,
            api_key=decrypt(item.connect_api_key_encrypted),
        )
        is_connected = await connect.test_connection()
        if not is_connected:
            item.add_tag("CONNECT-ERROR")
            item.remove_tag("CONNECT-READY")
            db.commit()
            return {"connected": False, "error": "Failed to ping CONNECT server."}
        
        company_filter = item.connect_backend_company or item.name
        filters = [["disabled", "=", 0]]
        fallback_used = False
        try:
            res = await connect.get_connect_items(fields=["name", "item_name", "item_code", "item_mrp"], filters=filters)
            products = res.get("data", [])
        except Exception as exc:
            logger.warning("CONNECT fetch failed: %s", exc)
            products = []

        from app.models.product import Product
        fetched_erp_ids = [p.get("name") for p in products if p.get("name")]
        
        db.query(Product).filter((Product.company_profile_id == item.id) & Product.erp_id.like("PROD-%")).update({"is_active": False}, synchronize_session=False)
        if fetched_erp_ids:
            db.query(Product).filter(
                (Product.company_profile_id == item.id) & 
                (Product.primary_category == "Connect") &
                (~Product.erp_id.in_(fetched_erp_ids))
            ).update({"is_active": False}, synchronize_session=False)
        
        # Fetch full product details concurrently to extract GST rates from taxes child table
        erp_ids = [p.get("name") for p in products if p.get("name")]
        details = await asyncio.gather(*[connect.fetch_product_detail(eid) for eid in erp_ids], return_exceptions=True)
        details_map = {}
        for eid, detail in zip(erp_ids, details):
            if isinstance(detail, Exception) or not detail:
                details_map[eid] = {}
            else:
                details_map[eid] = detail

        for p in products:
            taxes_list = details_map.get(p.get("name"), {}).get("taxes", [])
            p["gst_rate"] = _extract_gst_from_taxes(taxes_list)

        upserted_count = 0
        from decimal import Decimal
        for p in products:
            erp_id = p.get("name")
            if not erp_id:
                continue
            name = p.get("item_name") or erp_id
            mrp_val = Decimal(str(p.get("item_mrp") or p.get("standard_rate") or p.get("last_purchase_rate") or 0))
            category_val = "Connect"
            sku_val = p.get("item_code") or erp_id
            
            existing_product = db.query(Product).filter(Product.erp_id == erp_id).first()
            if existing_product:
                existing_product.name = name
                existing_product.company_profile_id = item.id
                existing_product.is_active = True
                existing_product.mrp = mrp_val
                existing_product.gst_rate = Decimal(str(p.get("gst_rate") or 0))
                existing_product.primary_category = category_val
                existing_product.sku = sku_val
            else:
                db.add(Product(
                    erp_id=erp_id,
                    name=name,
                    company_profile_id=item.id,
                    is_active=True,
                    mrp=mrp_val,
                    gst_rate=Decimal(str(p.get("gst_rate") or 0)),
                    primary_category=category_val,
                    sku=sku_val,
                ))
            upserted_count += 1
            
        if upserted_count > 0 or fetched_erp_ids:
            db.commit()
            logger.info("CONNECT: Successfully upserted %d products.", upserted_count)

        # Success Tagging
        item.add_tag("CONNECT-READY")
        item.remove_tag("CONNECT-ERROR")
        db.commit()

        message = "Connection test successful! Sastrybalm is communicating with the CONNECT distribution hub."
        if fallback_used and upserted_count > 0:
            message += f" (Note: Synced {upserted_count} products using fallback fetch)."
        elif upserted_count > 0:
            message += f" (Note: Synced {upserted_count} products using company filter '{company_filter}')."

        return {
            "connected": True,
            "message": message,
            "company_name": item.name,
            "backend_company": item.connect_backend_company,
            "products_found": len(products),
        }
    except Exception as exc:
        item.add_tag("CONNECT-ERROR")
        item.remove_tag("CONNECT-READY")
        db.commit()
        return {"connected": False, "error": f"Connection failed with error: {str(exc)}"}



@router.post("/profiles/test-zap-direct")
async def profile_test_zap_direct(
    base_url: str = Form(...),
    api_key: Optional[str] = Form(""),
    backend_company: Optional[str] = Form(""),
    profile_id: Optional[int] = Form(None),
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    from app.adapters.zap import ZapAdapter
    effective_api_key = api_key
    if not effective_api_key and profile_id:
        item = db.query(CompanyProfile).filter(CompanyProfile.id == profile_id).first()
        if item and item.zap_api_key_encrypted:
            effective_api_key = decrypt(item.zap_api_key_encrypted)
            
    if not base_url or not effective_api_key:
        return {"connected": False, "error": "ZAP Integration credentials not configured."}
        
    try:
        zap = ZapAdapter(
            base_url=base_url,
            api_key=effective_api_key,
        )
        is_connected = await zap.test_connection()
        if not is_connected:
            if profile_id:
                item = db.query(CompanyProfile).filter(CompanyProfile.id == profile_id).first()
                if item:
                    item.add_tag("ZAP-ERROR")
                    item.remove_tag("ZAP-READY")
                    db.commit()
            return {"connected": False, "error": "Failed to authenticate with ZAP server."}
            
        company_filter = backend_company or (db.query(CompanyProfile).filter(CompanyProfile.id == profile_id).first().name if profile_id else "")
        products = await zap.fetch_products(company_filter)
        
        fallback_used = False
        if not products and company_filter:
            products = await zap.fetch_products(None)
            fallback_used = True
            
        # Fetch full product details concurrently to extract GST rates from taxes child table
        erp_ids = [p.get("name") for p in products if p.get("name")]
        details = await asyncio.gather(*[zap.fetch_product_detail(eid) for eid in erp_ids], return_exceptions=True)
        details_map = {}
        for eid, detail in zip(erp_ids, details):
            if isinstance(detail, Exception) or not detail:
                details_map[eid] = {}
            else:
                details_map[eid] = detail

        for p in products:
            taxes_list = details_map.get(p.get("name"), {}).get("taxes", [])
            p["gst_rate"] = _extract_gst_from_taxes(taxes_list)

        upserted_count = 0
        if profile_id:
            item = db.query(CompanyProfile).filter(CompanyProfile.id == profile_id).first()
            if item:
                from app.models.product import Product
                import logging
                logger = logging.getLogger(__name__)
                
                fetched_erp_ids = [p.get("name") for p in products if p.get("name")]
                
                db.query(Product).filter((Product.company_profile_id == item.id) & Product.erp_id.like("PROD-%")).update({"is_active": False}, synchronize_session=False)
                if fetched_erp_ids:
                    db.query(Product).filter(
                        (Product.company_profile_id == item.id) & 
                        (Product.primary_category == "Products") &
                        (~Product.erp_id.in_(fetched_erp_ids))
                    ).update({"is_active": False}, synchronize_session=False)
                
                for p in products:
                    erp_id = p.get("name")
                    if not erp_id:
                        continue
                    name = p.get("item_name") or erp_id
                    mrp_val = Decimal(str(p.get("item_mrp") or p.get("standard_rate") or p.get("last_purchase_rate") or 0))
                    category_val = p.get("item_group") or "Products"
                    sku_val = p.get("item_code") or erp_id
                    
                    existing_product = db.query(Product).filter(Product.erp_id == erp_id).first()
                    if existing_product:
                        existing_product.name = name
                        existing_product.company_profile_id = item.id
                        existing_product.is_active = True
                        existing_product.mrp = mrp_val
                        existing_product.gst_rate = Decimal(str(p.get("gst_rate") or 0))
                        existing_product.primary_category = category_val
                        existing_product.sku = sku_val
                    else:
                        db.add(Product(
                            erp_id=erp_id,
                            name=name,
                            company_profile_id=item.id,
                            is_active=True,
                            mrp=mrp_val,
                            gst_rate=Decimal(str(p.get("gst_rate") or 0)),
                            primary_category=category_val,
                            sku=sku_val,
                        ))
                    upserted_count += 1
                    
                if upserted_count > 0 or fetched_erp_ids:
                    db.commit()
                    logger.info("ZAP: Successfully upserted %d products.", upserted_count)
                    
                item.add_tag("ZAP-READY")
                item.remove_tag("ZAP-ERROR")
                db.commit()

        message = "Connection test successful! Sastrybalm is communicating with the ZAP system."
        if fallback_used and len(products) > 0:
            message += f" (Note: Synced {len(products)} products using fallback fetch without company filter)."
        elif len(products) > 0:
            message += f" (Note: Synced {len(products)} products using company filter '{company_filter}')."
            
        return {
            "connected": True,
            "message": message,
            "products_found": len(products),
            "sample_products": products[:5],
        }
    except Exception as exc:
        if profile_id:
            item = db.query(CompanyProfile).filter(CompanyProfile.id == profile_id).first()
            if item:
                item.add_tag("ZAP-ERROR")
                item.remove_tag("ZAP-READY")
                db.commit()
        return {"connected": False, "error": f"Connection failed with error: {str(exc)}"}


@router.post("/profiles/test-cmms-direct")
async def profile_test_cmms_direct(
    base_url: str = Form(...),
    api_key: Optional[str] = Form(""),
    backend_company: Optional[str] = Form(""),
    profile_id: Optional[int] = Form(None),
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    from app.adapters.cmms import CMSAdapter
    import json
    import logging
    logger = logging.getLogger(__name__)
    effective_api_key = api_key
    if not effective_api_key and profile_id:
        item = db.query(CompanyProfile).filter(CompanyProfile.id == profile_id).first()
        if item and item.cmms_api_key_encrypted:
            effective_api_key = decrypt(item.cmms_api_key_encrypted)
            
    if not base_url or not effective_api_key:
        return {"connected": False, "error": "CMMS Integration credentials not configured."}
        
    try:
        cmms = CMSAdapter(
            base_url=base_url,
            api_key=effective_api_key,
        )
        is_connected = await cmms.test_connection()
        if not is_connected:
            if profile_id:
                item = db.query(CompanyProfile).filter(CompanyProfile.id == profile_id).first()
                if item:
                    item.add_tag("CMMS-ERROR")
                    item.remove_tag("CMMS-READY")
                    db.commit()
            return {"connected": False, "error": "Failed to ping CMMS server."}
            
        company_filter = backend_company or (db.query(CompanyProfile).filter(CompanyProfile.id == profile_id).first().name if profile_id else "")
        
        # Define the three base filters for Consumable items
        filters_1 = [["item_group", "=", "Consumable"], ["is_fixed_asset", "=", 1], ["is_stock_item", "=", 0], ["disabled", "=", 0]]
        filters_2 = [["item_group", "=", "Consumable"], ["is_fixed_asset", "=", 0], ["is_stock_item", "=", 1], ["disabled", "=", 0]]
        filters_3 = [["item_group", "=", "Consumable"], ["is_fixed_asset", "=", 0], ["is_stock_item", "=", 0], ["disabled", "=", 0]]
        
        async def fetch_type(filters_list):
            import copy
            f = copy.deepcopy(filters_list)
            if company_filter:
                f.append(["Item Default", "company", "=", company_filter])
            params = {
                "fields": json.dumps(["name", "item_name", "item_code", "item_group", "standard_rate"]),
                "limit_page_length": 0,
                "filters": json.dumps(f)
            }
            try:
                res = await cmms._request_with_retry("GET", "/api/resource/Item", params=params)
                data = res.get("data", [])
                if not data and company_filter:
                    f_fallback = copy.deepcopy(filters_list)
                    params["filters"] = json.dumps(f_fallback)
                    res = await cmms._request_with_retry("GET", "/api/resource/Item", params=params)
                    return res.get("data", [])
                return data
            except Exception:
                f_fallback = copy.deepcopy(filters_list)
                params["filters"] = json.dumps(f_fallback)
                try:
                    res = await cmms._request_with_retry("GET", "/api/resource/Item", params=params)
                    return res.get("data", [])
                except Exception:
                    return []
                
        products_1 = await fetch_type(filters_1)
        products_2 = await fetch_type(filters_2)
        products_3 = await fetch_type(filters_3)
        
        merged_products = {}
        for p in (products_1 + products_2 + products_3):
            code = p.get("name")
            if code:
                merged_products[code] = p
        products = list(merged_products.values())
        fallback_used = False

        # Fetch full product details concurrently to extract GST rates from taxes child table
        erp_ids = [p.get("name") for p in products if p.get("name")]
        details = await asyncio.gather(*[cmms.fetch_product_detail(eid) for eid in erp_ids], return_exceptions=True)
        details_map = {}
        for eid, detail in zip(erp_ids, details):
            if isinstance(detail, Exception) or not detail:
                details_map[eid] = {}
            else:
                details_map[eid] = detail

        for p in products:
            taxes_list = details_map.get(p.get("name"), {}).get("taxes", [])
            p["gst_rate"] = _extract_gst_from_taxes(taxes_list)

        upserted_count = 0
        if profile_id:
            item = db.query(CompanyProfile).filter(CompanyProfile.id == profile_id).first()
            if item:
                from app.models.product import Product
                fetched_erp_ids = [p.get("name") for p in products if p.get("name")]
                
                db.query(Product).filter((Product.company_profile_id == item.id) & Product.erp_id.like("PROD-%")).update({"is_active": False}, synchronize_session=False)
                if fetched_erp_ids:
                    db.query(Product).filter(
                        (Product.company_profile_id == item.id) & 
                        (Product.primary_category == "Consumable") &
                        (~Product.erp_id.in_(fetched_erp_ids))
                    ).update({"is_active": False}, synchronize_session=False)
                
                for p in products:
                    erp_id = p.get("name")
                    if not erp_id:
                        continue
                    name = p.get("item_name") or erp_id
                    mrp_val = Decimal(str(p.get("item_mrp") or p.get("standard_rate") or p.get("last_purchase_rate") or 0))
                    category_val = p.get("item_group") or "Consumable"
                    sku_val = p.get("item_code") or erp_id
                    
                    existing_product = db.query(Product).filter(Product.erp_id == erp_id).first()
                    if existing_product:
                        existing_product.name = name
                        existing_product.company_profile_id = item.id
                        existing_product.is_active = True
                        existing_product.mrp = mrp_val
                        existing_product.gst_rate = Decimal(str(p.get("gst_rate") or 0))
                        existing_product.primary_category = category_val
                        existing_product.sku = sku_val
                    else:
                        db.add(Product(
                            erp_id=erp_id,
                            name=name,
                            company_profile_id=item.id,
                            is_active=True,
                            mrp=mrp_val,
                            gst_rate=Decimal(str(p.get("gst_rate") or 0)),
                            primary_category=category_val,
                            sku=sku_val,
                        ))
                    upserted_count += 1
                    
                if upserted_count > 0 or fetched_erp_ids:
                    db.commit()
                    logger.info("CMMS: Successfully upserted %d products.", upserted_count)

                item.add_tag("CMMS-READY")
                item.remove_tag("CMMS-ERROR")
                db.commit()

        message = "Connection test successful! Sastrybalm is communicating with the CMMS platform."
        if fallback_used and len(products) > 0:
            message += f" (Note: Synced {len(products)} products using fallback fetch)."
        elif len(products) > 0:
            message += f" (Note: Synced {len(products)} products using company filter '{company_filter}')."

        return {
            "connected": True,
            "message": message,
            "products_found": len(products),
        }
    except Exception as exc:
        if profile_id:
            item = db.query(CompanyProfile).filter(CompanyProfile.id == profile_id).first()
            if item:
                item.add_tag("CMMS-ERROR")
                item.remove_tag("CMMS-READY")
                db.commit()
        return {"connected": False, "error": f"Connection failed with error: {str(exc)}"}


@router.post("/profiles/test-connect-direct")
async def profile_test_connect_direct(
    base_url: str = Form(...),
    api_key: Optional[str] = Form(""),
    backend_company: Optional[str] = Form(""),
    profile_id: Optional[int] = Form(None),
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    from app.adapters.connect import ConnectAdapter
    import logging
    logger = logging.getLogger(__name__)
    effective_api_key = api_key
    if not effective_api_key and profile_id:
        item = db.query(CompanyProfile).filter(CompanyProfile.id == profile_id).first()
        if item and item.connect_api_key_encrypted:
            effective_api_key = decrypt(item.connect_api_key_encrypted)
            
    if not base_url or not effective_api_key:
        return {"connected": False, "error": "CONNECT Integration credentials not configured."}
        
    try:
        connect = ConnectAdapter(
            base_url=base_url,
            api_key=effective_api_key,
        )
        is_connected = await connect.test_connection()
        if not is_connected:
            if profile_id:
                item = db.query(CompanyProfile).filter(CompanyProfile.id == profile_id).first()
                if item:
                    item.add_tag("CONNECT-ERROR")
                    item.remove_tag("CONNECT-READY")
                    db.commit()
            return {"connected": False, "error": "Failed to ping CONNECT server."}
            
        company_filter = backend_company or (db.query(CompanyProfile).filter(CompanyProfile.id == profile_id).first().name if profile_id else "")
        filters = [["disabled", "=", 0]]
        fallback_used = False
        try:
            res = await connect.get_connect_items(fields=["name", "item_name", "item_code", "item_mrp"], filters=filters)
            products = res.get("data", [])
        except Exception as exc:
            logger.warning("CONNECT fetch failed: %s", exc)
            products = []

        upserted_count = 0
        if profile_id:
            item = db.query(CompanyProfile).filter(CompanyProfile.id == profile_id).first()
            if item:
                from app.models.product import Product
                fetched_erp_ids = [p.get("name") for p in products if p.get("name")]
                
                db.query(Product).filter((Product.company_profile_id == item.id) & Product.erp_id.like("PROD-%")).update({"is_active": False}, synchronize_session=False)
                if fetched_erp_ids:
                    db.query(Product).filter(
                        (Product.company_profile_id == item.id) & 
                        (Product.primary_category == "Connect") &
                        (~Product.erp_id.in_(fetched_erp_ids))
                    ).update({"is_active": False}, synchronize_session=False)
                
                # Fetch full product details concurrently to extract GST rates from taxes child table
                erp_ids = [p.get("name") for p in products if p.get("name")]
                details = await asyncio.gather(*[connect.fetch_product_detail(eid) for eid in erp_ids], return_exceptions=True)
                details_map = {}
                for eid, detail in zip(erp_ids, details):
                    if isinstance(detail, Exception) or not detail:
                        details_map[eid] = {}
                    else:
                        details_map[eid] = detail

                for p in products:
                    taxes_list = details_map.get(p.get("name"), {}).get("taxes", [])
                    p["gst_rate"] = _extract_gst_from_taxes(taxes_list)

                for p in products:
                    erp_id = p.get("name")
                    if not erp_id:
                        continue
                    name = p.get("item_name") or erp_id
                    mrp_val = Decimal(str(p.get("item_mrp") or p.get("standard_rate") or p.get("last_purchase_rate") or 0))
                    category_val = "Connect"
                    sku_val = p.get("item_code") or erp_id
                    
                    existing_product = db.query(Product).filter(Product.erp_id == erp_id).first()
                    if existing_product:
                        existing_product.name = name
                        existing_product.company_profile_id = item.id
                        existing_product.is_active = True
                        existing_product.mrp = mrp_val
                        existing_product.gst_rate = Decimal(str(p.get("gst_rate") or 0))
                        existing_product.primary_category = category_val
                        existing_product.sku = sku_val
                    else:
                        db.add(Product(
                            erp_id=erp_id,
                            name=name,
                            company_profile_id=item.id,
                            is_active=True,
                            mrp=mrp_val,
                            gst_rate=Decimal(str(p.get("gst_rate") or 0)),
                            primary_category=category_val,
                            sku=sku_val,
                        ))
                    upserted_count += 1
                    
                if upserted_count > 0 or fetched_erp_ids:
                    db.commit()
                    logger.info("CONNECT: Successfully upserted %d products.", upserted_count)

                item.add_tag("CONNECT-READY")
                item.remove_tag("CONNECT-ERROR")
                db.commit()

        message = "Connection test successful! Sastrybalm is communicating with the CONNECT distribution hub."
        if fallback_used and len(products) > 0:
            message += f" (Note: Synced {len(products)} products using fallback fetch)."
        elif len(products) > 0:
            message += f" (Note: Synced {len(products)} products using company filter '{company_filter}')."

        return {
            "connected": True,
            "message": message,
            "products_found": len(products),
        }
    except Exception as exc:
        if profile_id:
            item = db.query(CompanyProfile).filter(CompanyProfile.id == profile_id).first()
            if item:
                item.add_tag("CONNECT-ERROR")
                item.remove_tag("CONNECT-READY")
                db.commit()
        return {"connected": False, "error": f"Connection failed with error: {str(exc)}"}


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
    zap_fetch_interval_minutes: int = Form(default=60),
    cmms_post_interval_minutes: int = Form(default=30),
    connect_sync_interval_minutes: int = Form(default=30),
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
    config.zap_fetch_interval_minutes = max(5, zap_fetch_interval_minutes)
    config.cmms_post_interval_minutes = max(5, cmms_post_interval_minutes)
    config.connect_sync_interval_minutes = max(5, connect_sync_interval_minutes)
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
    current_user: User = Depends(require_web_auth),
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
    
    mappings = db.query(ProductAliasMap).filter(ProductAliasMap.company_profile_id == profile_id).all()
    products = db.query(Product).filter(Product.is_active == True).order_by(Product.name).all()
    
    return templates.TemplateResponse("company/product_mappings.html", {
        "request": request, "current_user": current_user,
        "profile": profile, "mappings": mappings, "products": products,
        **get_flash(request),
    })


@router.post("/profiles/{profile_id}/product-mappings/new")
async def product_mapping_create(
    profile_id: int, request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
    product_id: int = Form(...),
    zap_item_code: Optional[str] = Form(default=None),
    cmms_item_code: Optional[str] = Form(default=None),
    connect_item_code: Optional[str] = Form(default=None),
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
        zap_item_code=zap_item_code or None,
        cmms_item_code=cmms_item_code or None,
        connect_item_code=connect_item_code or None,
        conversion_factor=Decimal(str(conversion_factor)),
    )
    db.add(mapping)
    db.commit()
    set_flash_success(request, "Product mapping added.")
    return RedirectResponse(f"/company/profiles/{profile_id}/product-mappings", status_code=302)
 
 
@router.post("/profiles/{profile_id}/product-mappings/{mapping_id}/edit")
async def product_mapping_update(
    profile_id: int, mapping_id: int, request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
    zap_item_code: Optional[str] = Form(default=None),
    cmms_item_code: Optional[str] = Form(default=None),
    connect_item_code: Optional[str] = Form(default=None),
    conversion_factor: float = Form(default=1.0),
):
    if current_user.role != UserRole.admin and current_user.company_profile_id != profile_id:
        raise HTTPException(status_code=403, detail="Not authorized to access mappings for this company profile.")
        
    from app.models.product_mapping import ProductAliasMap
    from decimal import Decimal
    mapping = db.query(ProductAliasMap).filter(ProductAliasMap.id == mapping_id, ProductAliasMap.company_profile_id == profile_id).first()
    if mapping:
        mapping.zap_item_code = zap_item_code or None
        mapping.cmms_item_code = cmms_item_code or None
        mapping.connect_item_code = connect_item_code or None
        mapping.conversion_factor = Decimal(str(conversion_factor))
        db.commit()
        set_flash_success(request, "Product mapping updated.")
    return RedirectResponse(f"/company/profiles/{profile_id}/product-mappings", status_code=302)


@router.post("/profiles/{profile_id}/product-mappings/{mapping_id}/delete")
async def product_mapping_delete(
    profile_id: int, mapping_id: int, request: Request,
    current_user: User = Depends(require_web_auth),
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
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
):
    if current_user.role != UserRole.admin and current_user.company_profile_id != profile_id:
        raise HTTPException(status_code=403, detail="Not authorized to access mappings for this company profile.")
    profile = db.query(CompanyProfile).filter(CompanyProfile.id == profile_id).first()
    if not profile or not profile.is_active:
        set_flash_error(request, "Active profile not found.")
        return RedirectResponse("/company/profiles", status_code=302)
        
    from app.models.product_mapping import AccountAliasMap
    
    mappings = db.query(AccountAliasMap).filter(AccountAliasMap.company_profile_id == profile_id).all()
    
    return templates.TemplateResponse("company/account_mappings.html", {
        "request": request, "current_user": current_user,
        "profile": profile, "mappings": mappings,
        **get_flash(request),
    })


@router.post("/profiles/{profile_id}/account-mappings/new")
async def account_mapping_create(
    profile_id: int, request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
    account_name: str = Form(...),
    account_type: Optional[str] = Form(default=None),
    zap_account_code: Optional[str] = Form(default=None),
    cmms_account_code: Optional[str] = Form(default=None),
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
        zap_account_code=zap_account_code or None,
        cmms_account_code=cmms_account_code or None,
    )
    db.add(mapping)
    db.commit()
    set_flash_success(request, "Account mapping added.")
    return RedirectResponse(f"/company/profiles/{profile_id}/account-mappings", status_code=302)


@router.post("/profiles/{profile_id}/account-mappings/{mapping_id}/edit")
async def account_mapping_update(
    profile_id: int, mapping_id: int, request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
    account_name: str = Form(...),
    account_type: Optional[str] = Form(default=None),
    zap_account_code: Optional[str] = Form(default=None),
    cmms_account_code: Optional[str] = Form(default=None),
):
    if current_user.role != UserRole.admin and current_user.company_profile_id != profile_id:
        raise HTTPException(status_code=403, detail="Not authorized to access mappings for this company profile.")
        
    from app.models.product_mapping import AccountAliasMap
    mapping = db.query(AccountAliasMap).filter(AccountAliasMap.id == mapping_id, AccountAliasMap.company_profile_id == profile_id).first()
    if mapping:
        mapping.account_name = account_name
        mapping.account_type = account_type or None
        mapping.zap_account_code = zap_account_code or None
        mapping.cmms_account_code = cmms_account_code or None
        db.commit()
        set_flash_success(request, "Account mapping updated.")
    return RedirectResponse(f"/company/profiles/{profile_id}/account-mappings", status_code=302)


@router.post("/profiles/{profile_id}/account-mappings/{mapping_id}/delete")
async def account_mapping_delete(
    profile_id: int, mapping_id: int, request: Request,
    current_user: User = Depends(require_web_auth),
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
