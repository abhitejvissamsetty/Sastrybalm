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

router = APIRouter(prefix="/vendors", tags=["vendors"])
templates = Jinja2Templates(directory="app/templates")

_ADMIN = require_web_roles(UserRole.admin, UserRole.territory_manager)


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
    if current_user.role == UserRole.territory_manager and current_user.geography_id:
        query = query.filter(Vendor.geography_id == current_user.geography_id)
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


from app.models.geography import Geography
from app.models.product import Product, ProductCategory


def _vendor_form_context(db: Session) -> dict:
    geographies = db.query(Geography).filter(Geography.is_active == True).order_by(Geography.name).all()
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
        "item": None, "error": None, **_vendor_form_context(db),
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
            "item": None, "error": f"Mobile '{mobile}' already registered.", **_vendor_form_context(db),
        })

    assigned_geo_id = int(geography_id) if geography_id else None
    if current_user.role == UserRole.territory_manager and current_user.geography_id:
        assigned_geo_id = current_user.geography_id

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
    return RedirectResponse("/vendors", status_code=302)


@router.get("/{vendor_id}/edit", response_class=HTMLResponse)
async def vendor_edit(
    vendor_id: int, request: Request,
    current_user: User = Depends(_ADMIN),
    db: Session = Depends(get_db),
):
    item = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not item:
        set_flash_error(request, "Vendor not found.")
        return RedirectResponse("/vendors", status_code=302)
    if current_user.role == UserRole.territory_manager and current_user.geography_id:
        if item.geography_id and item.geography_id != current_user.geography_id:
            set_flash_error(request, "Access denied. Territory Managers can only edit vendors assigned to their region.")
            return RedirectResponse("/vendors", status_code=302)
    return templates.TemplateResponse("vendors/form.html", {
        "request": request, "current_user": current_user,
        "item": item, "error": None, **_vendor_form_context(db),
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
        return RedirectResponse("/vendors", status_code=302)
    if current_user.role == UserRole.territory_manager and current_user.geography_id:
        if item.geography_id and item.geography_id != current_user.geography_id:
            set_flash_error(request, "Access denied. Territory Managers can only edit vendors assigned to their region.")
            return RedirectResponse("/vendors", status_code=302)

    assigned_geo_id = int(geography_id) if geography_id else None
    if current_user.role == UserRole.territory_manager and current_user.geography_id:
        assigned_geo_id = current_user.geography_id

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
    item.address = address or None
    if new_password:
        item.hashed_password = hash_password(new_password)

    item.supplied_products.clear()
    if product_ids:
        p_objs = db.query(Product).filter(Product.id.in_(product_ids)).all()
        item.supplied_products.extend(p_objs)

    db.commit()
    set_flash_success(request, f"Vendor '{name}' updated.")
    return RedirectResponse("/vendors", status_code=302)


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
    return RedirectResponse("/vendors", status_code=302)


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
        return RedirectResponse("/vendors", status_code=302)
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
