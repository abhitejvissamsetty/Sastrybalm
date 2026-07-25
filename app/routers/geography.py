from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_web_auth, require_web_roles
from app.models.geography import Geography, GeoLevel
from app.models.user import User, UserRole
from app.utils.flash import get_flash, set_flash_error, set_flash_success
from app.utils.pagination import paginate

router = APIRouter(prefix="/geography", tags=["geography"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def geo_list(
    request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
    q: str = Query(default=""),
    level: str = Query(default=""),
    page: int = Query(default=1, ge=1),
):
    query = db.query(Geography)
    if q:
        query = query.filter(
            Geography.name.ilike(f"%{q}%") | Geography.code.ilike(f"%{q}%")
        )
    if level and level in [lv.value for lv in GeoLevel]:
        query = query.filter(Geography.level == level)
    query = query.order_by(Geography.level, Geography.name)
    pagination = paginate(query, page)
    return templates.TemplateResponse("geography/list.html", {
        "request": request, "current_user": current_user,
        "pagination": pagination, "q": q, "level": level,
        "GeoLevel": GeoLevel, **get_flash(request),
    })


from app.models.warehouse import Warehouse


@router.get("/new", response_class=HTMLResponse)
async def geo_new(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
):
    parents = db.query(Geography).filter(Geography.is_active == True).order_by(Geography.level, Geography.name).all()
    warehouses = db.query(Warehouse).filter(Warehouse.is_active == True).order_by(Warehouse.name).all()
    return templates.TemplateResponse("geography/form.html", {
        "request": request, "current_user": current_user,
        "item": None, "parents": parents, "warehouses": warehouses, "GeoLevel": GeoLevel, "error": None,
    })


@router.post("/new")
async def geo_create(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
    name: str = Form(...),
    code: str = Form(...),
    level: str = Form(...),
    parent_id: Optional[str] = Form(default=None),
    erp_id: Optional[str] = Form(default=None),
    warehouse_ids: list[str] = Form(default=[]),
):
    parent_id_int = int(parent_id) if parent_id else None
    err = _validate_hierarchy(db, GeoLevel(level), parent_id_int)
    if not err and db.query(Geography).filter(Geography.code == code.upper()).first():
        err = f"Code '{code.upper()}' already exists."
    if err:
        parents = db.query(Geography).filter(Geography.is_active == True).order_by(Geography.level, Geography.name).all()
        warehouses = db.query(Warehouse).filter(Warehouse.is_active == True).order_by(Warehouse.name).all()
        return templates.TemplateResponse("geography/form.html", {
            "request": request, "current_user": current_user,
            "item": None, "parents": parents, "warehouses": warehouses, "GeoLevel": GeoLevel, "error": err,
        })

    geo = Geography(name=name, code=code.upper(), level=GeoLevel(level), parent_id=parent_id_int, erp_id=erp_id or None)
    db.add(geo)
    db.flush()

    if level == GeoLevel.region.value:
        selected_wh_ids = [int(w) for w in warehouse_ids if w and str(w).isdigit()]
        if selected_wh_ids:
            whs = db.query(Warehouse).filter(Warehouse.id.in_(selected_wh_ids)).all()
            for wh in whs:
                wh.geography_id = geo.id

    db.commit()
    set_flash_success(request, f"Geography '{name}' created.")
    return RedirectResponse("/geography", status_code=302)


@router.get("/{geo_id}/edit", response_class=HTMLResponse)
async def geo_edit(
    geo_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
):
    item = db.query(Geography).filter(Geography.id == geo_id).first()
    if not item:
        set_flash_error(request, "Geography not found.")
        return RedirectResponse("/geography", status_code=302)
    if not item.is_active:
        set_flash_error(request, "Cannot edit a deactivated geography.")
        return RedirectResponse("/geography", status_code=302)
    parents = db.query(Geography).filter(Geography.is_active == True, Geography.id != geo_id).order_by(Geography.level, Geography.name).all()
    warehouses = db.query(Warehouse).filter(Warehouse.is_active == True).order_by(Warehouse.name).all()
    return templates.TemplateResponse("geography/form.html", {
        "request": request, "current_user": current_user,
        "item": item, "parents": parents, "warehouses": warehouses, "GeoLevel": GeoLevel, "error": None,
    })


@router.post("/{geo_id}/edit")
async def geo_update(
    geo_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
    name: str = Form(...),
    code: str = Form(...),
    level: str = Form(...),
    parent_id: Optional[str] = Form(default=None),
    erp_id: Optional[str] = Form(default=None),
    warehouse_ids: list[str] = Form(default=[]),
):
    item = db.query(Geography).filter(Geography.id == geo_id).first()
    if not item:
        set_flash_error(request, "Geography not found.")
        return RedirectResponse("/geography", status_code=302)
    if not item.is_active:
        set_flash_error(request, "Cannot edit a deactivated geography.")
        return RedirectResponse("/geography", status_code=302)
    parent_id_int = int(parent_id) if parent_id else None
    err = _validate_hierarchy(db, GeoLevel(level), parent_id_int)
    if not err and db.query(Geography).filter(Geography.code == code.upper(), Geography.id != geo_id).first():
        err = f"Code '{code.upper()}' already in use."
    
    if not err and item.level != GeoLevel(level):
        # Check active child geographies
        active_children = db.query(Geography).filter(Geography.parent_id == item.id, Geography.is_active == True).count()
        if active_children > 0:
            err = f"Cannot change level of '{item.name}' because it has active child geographies."
        else:
            # Check active beats linked
            from app.models.beat import Beat
            active_beats = db.query(Beat).filter(Beat.territory_id == item.id, Beat.is_active == True).count()
            if active_beats > 0:
                err = f"Cannot change level of '{item.name}' because it is attached to active beats."

    if err:
        parents = db.query(Geography).filter(Geography.is_active == True, Geography.id != geo_id).order_by(Geography.level, Geography.name).all()
        warehouses = db.query(Warehouse).filter(Warehouse.is_active == True).order_by(Warehouse.name).all()
        return templates.TemplateResponse("geography/form.html", {
            "request": request, "current_user": current_user,
            "item": item, "parents": parents, "warehouses": warehouses, "GeoLevel": GeoLevel, "error": err,
        })

    item.name = name
    item.code = code.upper()
    item.level = GeoLevel(level)
    item.parent_id = parent_id_int
    item.erp_id = erp_id or None

    if level == GeoLevel.region.value:
        form_data = await request.form()
        raw_wh_ids = form_data.getlist("warehouse_ids")
        selected_wh_ids = [int(w) for w in (raw_wh_ids or warehouse_ids) if w and str(w).isdigit()]
        
        # Clear warehouses previously mapped to this region if unselected
        old_whs = db.query(Warehouse).filter(Warehouse.geography_id == item.id).all()
        for ow in old_whs:
            if ow.id not in selected_wh_ids:
                ow.geography_id = None
                
        # Assign new warehouses
        if selected_wh_ids:
            new_whs = db.query(Warehouse).filter(Warehouse.id.in_(selected_wh_ids)).all()
            for nw in new_whs:
                nw.geography_id = item.id

    db.commit()
    set_flash_success(request, f"Geography '{name}' updated.")
    return RedirectResponse("/geography", status_code=302)


@router.post("/{geo_id}/delete")
async def geo_delete(
    geo_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    item = db.query(Geography).filter(Geography.id == geo_id).first()
    if item:
        # Check active child geographies
        active_children = db.query(Geography).filter(Geography.parent_id == item.id, Geography.is_active == True).count()
        if active_children > 0:
            set_flash_error(request, f"Cannot deactivate '{item.name}' because it has active child geographies.")
            return RedirectResponse("/geography", status_code=302)
        
        # Check active beats linked to this territory
        from app.models.beat import Beat
        active_beats = db.query(Beat).filter(Beat.territory_id == item.id, Beat.is_active == True).count()
        if active_beats > 0:
            set_flash_error(request, f"Cannot deactivate '{item.name}' because it is attached to active beats.")
            return RedirectResponse("/geography", status_code=302)
            
        item.is_active = False
        db.commit()
        set_flash_success(request, f"'{item.name}' deactivated.")
    return RedirectResponse("/geography", status_code=302)


@router.post("/{geo_id}/activate")
async def geo_activate(
    geo_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    item = db.query(Geography).filter(Geography.id == geo_id).first()
    if item:
        # Check if parent is active (if not top-level zone)
        if item.parent_id:
            parent = db.query(Geography).filter(Geography.id == item.parent_id).first()
            if parent and not parent.is_active:
                set_flash_error(request, f"Cannot activate '{item.name}' because its parent geography '{parent.name}' is deactivated.")
                return RedirectResponse("/geography", status_code=302)
                
        item.is_active = True
        db.commit()
        set_flash_success(request, f"'{item.name}' activated.")
    return RedirectResponse("/geography", status_code=302)


def _validate_hierarchy(db, level: GeoLevel, parent_id: Optional[int]) -> Optional[str]:
    if level == GeoLevel.zone and parent_id:
        return "Zone cannot have a parent."
    if level == GeoLevel.region:
        if not parent_id:
            return "Region must have a Zone parent."
        p = db.query(Geography).filter(Geography.id == parent_id).first()
        if not p or p.level != GeoLevel.zone:
            return "Region's parent must be a Zone."
    if level == GeoLevel.territory:
        if not parent_id:
            return "Territory must have a Region parent."
        p = db.query(Geography).filter(Geography.id == parent_id).first()
        if not p or p.level != GeoLevel.region:
            return "Territory's parent must be a Region."
    return None
