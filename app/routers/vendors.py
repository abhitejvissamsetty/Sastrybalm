"""
Vendor Management router — Admin CRUD for vendors and vendor employees.
Vendors are mobile-only with separate login.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_web_roles
from app.models.user import User, UserRole
from app.models.vendor import Vendor, VendorEmployee, VendorStatus
from app.utils.flash import get_flash, set_flash_error, set_flash_success
from app.utils.pagination import paginate
from app.utils.security import hash_password

router = APIRouter(prefix="/master-data/vendors", tags=["vendors"])
templates = Jinja2Templates(directory="app/templates")

_ADMIN = require_web_roles(UserRole.admin, UserRole.territory_manager)


from app.utils.geography_scope import get_user_allowed_geography_ids

@router.get("", response_class=HTMLResponse)
async def vendor_list(
    request: Request,
    current_user: User = Depends(_ADMIN),
    db: Session = Depends(get_db),
    q: str = Query(default=""),
    status: str = Query(default=""),
    page: int = Query(default=1, ge=1),
):
    query = db.query(Vendor)
    allowed_geo_ids = get_user_allowed_geography_ids(current_user, db)
    if allowed_geo_ids is not None:
        query = query.filter(Vendor.geography_id.in_(allowed_geo_ids))
    if q:
        query = query.filter(Vendor.name.ilike(f"%{q}%") | Vendor.mobile.ilike(f"%{q}%"))
    if status and status in [s.value for s in VendorStatus]:
        query = query.filter(Vendor.status == status)
    query = query.order_by(Vendor.name)
    pagination = paginate(query, page)
    return templates.TemplateResponse("vendors/list.html", {
        "request": request, "current_user": current_user,
        "pagination": pagination, "q": q, "status": status,
        "VendorStatus": VendorStatus, **get_flash(request),
    })


from app.models.geography import Geography, GeoLevel
from app.models.product import Product, ProductCategory


def _vendor_form_context(db: Session, user: Optional[User] = None) -> dict:
    geo_query = db.query(Geography).filter(Geography.is_active == True, Geography.level == GeoLevel.region)
    if user:
        allowed_geo_ids = get_user_allowed_geography_ids(user, db)
        if allowed_geo_ids is not None:
            geo_query = geo_query.filter(Geography.id.in_(allowed_geo_ids))

    geographies = geo_query.order_by(Geography.name).all()
    products = db.query(Product).filter(
        Product.is_active == True,
        Product.category_type == ProductCategory.marketing_procurement
    ).order_by(Product.name).all()
    return {
        "geographies": geographies,
        "products": products,
    }


@router.get("/new", response_class=HTMLResponse)
async def vendor_new(
    request: Request,
    current_user: User = Depends(_ADMIN),
    db: Session = Depends(get_db),
):
    return templates.TemplateResponse("vendors/form.html", {
        "request": request, "current_user": current_user,
        "item": None, "error": None, **_vendor_form_context(db, current_user),
    })


@router.post("/new")
async def vendor_create(
    request: Request,
    current_user: User = Depends(_ADMIN),
    db: Session = Depends(get_db),
    name: str = Form(...),
    contact_person: Optional[str] = Form(default=None),
    mobile: Optional[str] = Form(default=None),
    email: Optional[str] = Form(default=None),
    category: Optional[str] = Form(default=None),
    cmms_supplier_ref: Optional[str] = Form(default=None),
    geography_id: Optional[str] = Form(default=None),
    product_ids: list[str] = Form(default=[]),
    password: Optional[str] = Form(default=None),
    address: Optional[str] = Form(default=None),
):
    if mobile and db.query(Vendor).filter(Vendor.mobile == mobile).first():
        return templates.TemplateResponse("vendors/form.html", {
            "request": request, "current_user": current_user,
            "item": None, "error": f"Mobile '{mobile}' already registered.", **_vendor_form_context(db, current_user),
        })

    assigned_geo_id = int(geography_id) if geography_id else None
    allowed_geo_ids = get_user_allowed_geography_ids(current_user, db)
    if allowed_geo_ids is not None:
        if not assigned_geo_id or assigned_geo_id not in allowed_geo_ids:
            assigned_geo_id = allowed_geo_ids[0] if allowed_geo_ids else None

    v = Vendor(
        name=name,
        contact_person=contact_person or None,
        mobile=mobile or None,
        email=email or None,
        category=category or None,
        cmms_supplier_ref=cmms_supplier_ref or None,
        geography_id=assigned_geo_id,
        hashed_password=hash_password(password) if password else None,
        address=address or None,
    )
    if product_ids:
        p_objs = db.query(Product).filter(Product.id.in_(product_ids)).all()
        v.supplied_products.extend(p_objs)

    db.add(v)
    db.commit()
    set_flash_success(request, f"Vendor '{name}' created.")
    return RedirectResponse("/master-data/vendors", status_code=302)


@router.get("/{vendor_id}/edit", response_class=HTMLResponse)
async def vendor_edit(
    vendor_id: int, request: Request,
    current_user: User = Depends(_ADMIN),
    db: Session = Depends(get_db),
):
    item = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not item:
        set_flash_error(request, "Vendor not found.")
        return RedirectResponse("/master-data/vendors", status_code=302)
    allowed_geo_ids = get_user_allowed_geography_ids(current_user, db)
    if allowed_geo_ids is not None:
        if item.geography_id and item.geography_id not in allowed_geo_ids:
            set_flash_error(request, "Access denied. Territory Managers can only edit vendors assigned to their region.")
            return RedirectResponse("/master-data/vendors", status_code=302)
    return templates.TemplateResponse("vendors/form.html", {
        "request": request, "current_user": current_user,
        "item": item, "error": None, **_vendor_form_context(db, current_user),
    })


@router.post("/{vendor_id}/edit")
async def vendor_update(
    vendor_id: int, request: Request,
    current_user: User = Depends(_ADMIN),
    db: Session = Depends(get_db),
    name: str = Form(...),
    contact_person: Optional[str] = Form(default=None),
    mobile: Optional[str] = Form(default=None),
    email: Optional[str] = Form(default=None),
    category: Optional[str] = Form(default=None),
    cmms_supplier_ref: Optional[str] = Form(default=None),
    geography_id: Optional[str] = Form(default=None),
    product_ids: list[str] = Form(default=[]),
    new_password: Optional[str] = Form(default=None),
    address: Optional[str] = Form(default=None),
):
    item = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not item:
        set_flash_error(request, "Vendor not found.")
        return RedirectResponse("/master-data/vendors", status_code=302)
    allowed_geo_ids = get_user_allowed_geography_ids(current_user, db)
    if allowed_geo_ids is not None:
        if item.geography_id and item.geography_id not in allowed_geo_ids:
            set_flash_error(request, "Access denied. Territory Managers can only edit vendors assigned to their region.")
            return RedirectResponse("/master-data/vendors", status_code=302)

    assigned_geo_id = int(geography_id) if geography_id else None
    if allowed_geo_ids is not None:
        if not assigned_geo_id or assigned_geo_id not in allowed_geo_ids:
            assigned_geo_id = item.geography_id if item.geography_id in allowed_geo_ids else (allowed_geo_ids[0] if allowed_geo_ids else None)

    item.name = name
    item.contact_person = contact_person or None
    item.mobile = mobile or None
    item.email = email or None
    item.category = category or None
    item.cmms_supplier_ref = cmms_supplier_ref or None
    item.geography_id = assigned_geo_id
    item.address = address or None
    if new_password:
        item.hashed_password = hash_password(new_password)

    item.supplied_products.clear()
    if product_ids:
        p_objs = db.query(Product).filter(Product.id.in_(product_ids)).all()
        item.supplied_products.extend(p_objs)

    db.commit()
    set_flash_success(request, f"Vendor '{name}' updated.")
    return RedirectResponse("/master-data/vendors", status_code=302)


@router.post("/{vendor_id}/toggle")
async def vendor_toggle(
    vendor_id: int, request: Request,
    current_user: User = Depends(_ADMIN),
    db: Session = Depends(get_db),
):
    item = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if item:
        if item.status == VendorStatus.active:
            item.status = VendorStatus.inactive
            set_flash_success(request, f"'{item.name}' deactivated.")
        else:
            item.status = VendorStatus.active
            set_flash_success(request, f"'{item.name}' activated.")
        db.commit()
    return RedirectResponse("/master-data/vendors", status_code=302)


# ── Vendor Employees ───────────────────────────────────────────────────────────

@router.get("/{vendor_id}/employees", response_class=HTMLResponse)
async def employee_list(
    vendor_id: int, request: Request,
    current_user: User = Depends(_ADMIN),
    db: Session = Depends(get_db),
):
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        set_flash_error(request, "Vendor not found.")
        return RedirectResponse("/master-data/vendors", status_code=302)
    return templates.TemplateResponse("vendors/employees.html", {
        "request": request, "current_user": current_user,
        "vendor": vendor, "employees": vendor.employees,
        **get_flash(request),
    })


@router.post("/{vendor_id}/employees/add")
async def employee_add(
    vendor_id: int, request: Request,
    current_user: User = Depends(_ADMIN),
    db: Session = Depends(get_db),
    name: str = Form(...),
    mobile: Optional[str] = Form(default=None),
    email: Optional[str] = Form(default=None),
    password: Optional[str] = Form(default=None),
):
    emp = VendorEmployee(
        vendor_id=vendor_id,
        name=name,
        mobile=mobile or None,
        email=email or None,
        hashed_password=hash_password(password) if password else None,
    )
    db.add(emp)
    db.commit()
    set_flash_success(request, f"Employee '{name}' added.")
    return RedirectResponse(f"/vendors/{vendor_id}/employees", status_code=302)
