import csv
import io
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_web_auth, require_web_roles
from app.models.product import Product
from app.models.user import User, UserRole
from app.utils.csv_import import parse_csv_bytes
from app.utils.flash import get_flash, set_flash_error, set_flash_success
from app.utils.pagination import paginate

router = APIRouter(prefix="/products", tags=["products"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def product_list(
    request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
    q: str = Query(default=""),
    category: str = Query(default=""),
    must_sell: str = Query(default=""),
    company_profile_id: str = Query(default=""),
    page: int = Query(default=1, ge=1),
):
    if current_user.company_profile_id:
        company_profile_id = str(current_user.company_profile_id)

    if not company_profile_id:
        from app.models.company import CompanyProfile
        first_profile = db.query(CompanyProfile).filter(CompanyProfile.is_active == True).order_by(CompanyProfile.name).first()
        if first_profile:
            company_profile_id = str(first_profile.id)

    if not company_profile_id:
        pagination = None
    else:
        query = db.query(Product).filter(Product.company_profile_id == int(company_profile_id))
        if q:
            query = query.filter(Product.name.ilike(f"%{q}%") | Product.erp_id.ilike(f"%{q}%") | Product.sku.ilike(f"%{q}%"))
        if category:
            query = query.filter(Product.primary_category.ilike(f"%{category}%"))
        if must_sell == "yes":
            query = query.filter(Product.must_sell == True)
        elif must_sell == "no":
            query = query.filter(Product.must_sell == False)
        query = query.order_by(Product.name)
        pagination = paginate(query, page)
    mappings_dict = {}
    if company_profile_id:
        from app.models.product_mapping import ProductAliasMap
        maps = db.query(ProductAliasMap).filter(ProductAliasMap.company_profile_id == int(company_profile_id)).all()
        mappings_dict = {m.product_id: m for m in maps}
    
    from app.models.company import CompanyProfile
    if current_user.company_profile_id:
        profiles = db.query(CompanyProfile).filter(CompanyProfile.id == current_user.company_profile_id).all()
    else:
        profiles = db.query(CompanyProfile).filter(CompanyProfile.is_active == True).order_by(CompanyProfile.name).all()
    
    return templates.TemplateResponse("products/list.html", {
        "request": request, "current_user": current_user,
        "pagination": pagination, "q": q, "category": category, "must_sell": must_sell,
        "company_profile_id": company_profile_id, "profiles": profiles,
        "mappings_dict": mappings_dict,
        **get_flash(request),
    })


@router.get("/new", response_class=HTMLResponse)
async def product_new(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
):
    return templates.TemplateResponse("products/form.html", {
        "request": request, "current_user": current_user, "item": None, "error": None,
    })


@router.post("/new")
async def product_create(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
    name: str = Form(...),
    erp_id: Optional[str] = Form(default=None),
    sku: Optional[str] = Form(default=None),
    division: Optional[str] = Form(default=None),
    primary_category: Optional[str] = Form(default=None),
    secondary_category: Optional[str] = Form(default=None),
    mrp: Optional[str] = Form(default=None),
    gst_rate: Optional[str] = Form(default=None),
    must_sell: Optional[str] = Form(default=None),
):
    try:
        mrp_val = Decimal(mrp) if mrp else None
        gst_val = Decimal(gst_rate) if gst_rate else Decimal("0")
    except Exception:
        return templates.TemplateResponse("products/form.html", {
            "request": request, "current_user": current_user, "item": None,
            "error": "MRP and GST rate must be valid numbers.",
        })
    db.add(Product(
        name=name, erp_id=erp_id or None, sku=sku or None,
        division=division or None, primary_category=primary_category or None,
        secondary_category=secondary_category or None,
        mrp=mrp_val, gst_rate=gst_val, must_sell=must_sell == "on",
    ))
    db.commit()
    set_flash_success(request, f"Product '{name}' created.")
    return RedirectResponse("/products", status_code=302)


@router.get("/{product_id}/edit", response_class=HTMLResponse)
async def product_edit(
    product_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
):
    item = db.query(Product).filter(Product.id == product_id).first()
    if not item:
        set_flash_error(request, "Product not found.")
        return RedirectResponse("/products", status_code=302)
    return templates.TemplateResponse("products/form.html", {
        "request": request, "current_user": current_user, "item": item, "error": None,
    })


@router.post("/{product_id}/edit")
async def product_update(
    product_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
    name: str = Form(...),
    erp_id: Optional[str] = Form(default=None),
    sku: Optional[str] = Form(default=None),
    division: Optional[str] = Form(default=None),
    primary_category: Optional[str] = Form(default=None),
    secondary_category: Optional[str] = Form(default=None),
    mrp: Optional[str] = Form(default=None),
    gst_rate: Optional[str] = Form(default=None),
    must_sell: Optional[str] = Form(default=None),
    is_active: Optional[str] = Form(default=None),
):
    item = db.query(Product).filter(Product.id == product_id).first()
    if not item:
        set_flash_error(request, "Product not found.")
        return RedirectResponse("/products", status_code=302)
    try:
        item.mrp = Decimal(mrp) if mrp else None
        item.gst_rate = Decimal(gst_rate) if gst_rate else Decimal("0")
    except Exception:
        return templates.TemplateResponse("products/form.html", {
            "request": request, "current_user": current_user, "item": item,
            "error": "MRP and GST rate must be valid numbers.",
        })
    item.name = name
    item.erp_id = erp_id or None
    item.sku = sku or None
    item.division = division or None
    item.primary_category = primary_category or None
    item.secondary_category = secondary_category or None
    item.must_sell = must_sell == "on"
    item.is_active = is_active == "on"
    db.commit()
    set_flash_success(request, f"Product '{name}' updated.")
    return RedirectResponse("/products", status_code=302)


@router.post("/{product_id}/delete")
async def product_delete(
    product_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    item = db.query(Product).filter(Product.id == product_id).first()
    if item:
        item.is_active = False
        db.commit()
        set_flash_success(request, f"'{item.name}' deactivated.")
    return RedirectResponse("/products", status_code=302)


@router.post("/import")
async def product_import(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
):
    """CSV: name, erp_id, sku, division, primary_category, secondary_category, mrp, gst_rate, must_sell"""
    content = await file.read()
    rows = parse_csv_bytes(content)
    created = 0
    errors: list[str] = []
    for i, row in enumerate(rows, start=2):
        name = row.get("name", "").strip()
        if not name:
            errors.append(f"Row {i}: missing name")
            continue
        try:
            mrp_val = Decimal(row["mrp"]) if row.get("mrp") else None
            gst_val = Decimal(row["gst_rate"]) if row.get("gst_rate") else Decimal("0")
        except Exception:
            errors.append(f"Row {i}: invalid MRP/GST")
            continue
        db.add(Product(
            name=name, erp_id=row.get("erp_id") or None, sku=row.get("sku") or None,
            division=row.get("division") or None,
            primary_category=row.get("primary_category") or None,
            secondary_category=row.get("secondary_category") or None,
            mrp=mrp_val, gst_rate=gst_val,
            must_sell=row.get("must_sell", "").lower() in ("yes", "true", "1"),
        ))
        created += 1
    db.commit()
    msg = f"Imported {created} products."
    if errors:
        msg += f" {len(errors)} skipped: " + "; ".join(errors[:3])
        set_flash_error(request, msg)
    else:
        set_flash_success(request, msg)
    return RedirectResponse("/products", status_code=302)


@router.get("/export")
async def product_export(
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
):
    products = db.query(Product).order_by(Product.name).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "name", "erp_id", "sku", "division", "primary_category", "secondary_category", "mrp", "gst_rate", "must_sell", "is_active"])
    for p in products:
        writer.writerow([p.id, p.name, p.erp_id or "", p.sku or "", p.division or "",
                         p.primary_category or "", p.secondary_category or "",
                         p.mrp or "", p.gst_rate or "", "yes" if p.must_sell else "no",
                         "yes" if p.is_active else "no"])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=products.csv"},
    )
