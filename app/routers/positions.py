from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_web_auth, require_web_roles
from app.models.beat import Beat
from app.models.position import Position, PositionLevel
from app.models.user import User, UserRole
from app.utils.flash import get_flash, set_flash_error, set_flash_success
from app.utils.pagination import paginate

router = APIRouter(prefix="/master-data/positions", tags=["positions"])
templates = Jinja2Templates(directory="app/templates")


def validate_position_hierarchy(db: Session, level_str: str, reporting_to_id: Optional[str], current_pos_id: Optional[int] = None) -> Optional[str]:
    try:
        level = PositionLevel(level_str)
    except ValueError:
        return f"Invalid position level: {level_str}"
        
    if level == PositionLevel.L4:
        if reporting_to_id and reporting_to_id.strip() != "":
            return "L4 positions cannot report to any parent position."
    else:
        if not reporting_to_id or reporting_to_id.strip() == "":
            return f"Reports To is mandatory for {level.value} level position."
        
        try:
            rid = int(reporting_to_id)
        except ValueError:
            return "Invalid parent position selected."

        if current_pos_id and rid == current_pos_id:
            return "A position cannot report to itself."
            
        parent = db.query(Position).filter(Position.id == rid).first()
        if not parent:
            return "Parent position not found."
        if not parent.is_active:
            return f"Cannot report to inactive position '{parent.name}'."
            
        if level == PositionLevel.L3 and parent.level != PositionLevel.L4:
            return f"An L3 position must report to an L4 position (selected reports to level: {parent.level.value})."
        elif level == PositionLevel.L2 and parent.level != PositionLevel.L3:
            return f"An L2 position must report to an L3 position (selected reports to level: {parent.level.value})."
        elif level == PositionLevel.L1 and parent.level != PositionLevel.L2:
            return f"An L1 position must report to an L2 position (selected reports to level: {parent.level.value})."
            
    return None


@router.get("", response_class=HTMLResponse)
async def position_list(
    request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
    q: str = Query(default=""),
    level: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    tab: str = Query(default="active"),
):
    active_query = db.query(Position).filter(Position.is_active == True)
    inactive_query = db.query(Position).filter(Position.is_active == False)
    
    if q:
        active_query = active_query.filter(Position.name.ilike(f"%{q}%") | Position.code.ilike(f"%{q}%"))
        inactive_query = inactive_query.filter(Position.name.ilike(f"%{q}%") | Position.code.ilike(f"%{q}%"))
    if level and level in [lv.value for lv in PositionLevel]:
        active_query = active_query.filter(Position.level == level)
        inactive_query = inactive_query.filter(Position.level == level)
        
    active_count = active_query.count()
    inactive_count = inactive_query.count()

    if tab == "inactive":
        query = inactive_query
    else:
        query = active_query
        tab = "active"

    query = query.order_by(Position.level, Position.name)
    pagination = paginate(query, page)
    return templates.TemplateResponse("positions/list.html", {
        "request": request, "current_user": current_user,
        "pagination": pagination, "q": q, "level": level,
        "tab": tab,
        "active_count": active_count,
        "inactive_count": inactive_count,
        "PositionLevel": PositionLevel, **get_flash(request),
    })


from app.models.warehouse import Warehouse


@router.get("/new", response_class=HTMLResponse)
async def position_new(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
):
    managers = db.query(Position).filter(Position.is_active == True, Position.level != PositionLevel.L1).order_by(Position.name).all()
    beats = db.query(Beat).filter(Beat.is_active == True).order_by(Beat.name).all()
    users = db.query(User).filter(User.is_active == True, User.role != UserRole.admin).order_by(User.full_name).all()
    warehouses = db.query(Warehouse).filter(Warehouse.is_active == True).order_by(Warehouse.name).all()
    return templates.TemplateResponse("positions/form.html", {
        "request": request, "current_user": current_user,
        "item": None, "managers": managers, "beats": beats, "users": users, "warehouses": warehouses,
        "PositionLevel": PositionLevel, "error": None,
    })


@router.post("/new")
async def position_create(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
    name: str = Form(...),
    code: str = Form(...),
    level: str = Form(...),
    reporting_to_id: Optional[str] = Form(default=None),
    warehouse_id: Optional[str] = Form(default=None),
    beat_ids: list[str] = Form(default=[]),
    attached_user_id: Optional[str] = Form(default=None),
):
    def _form_context(err_msg: str):
        managers = db.query(Position).filter(Position.is_active == True, Position.level != PositionLevel.L1).order_by(Position.name).all()
        beats = db.query(Beat).filter(Beat.is_active == True).order_by(Beat.name).all()
        users = db.query(User).filter(User.is_active == True, User.role != UserRole.admin).order_by(User.full_name).all()
        warehouses = db.query(Warehouse).filter(Warehouse.is_active == True).order_by(Warehouse.name).all()
        return templates.TemplateResponse("positions/form.html", {
            "request": request, "current_user": current_user,
            "item": None, "managers": managers, "beats": beats, "users": users, "warehouses": warehouses,
            "PositionLevel": PositionLevel, "error": err_msg,
        })

    if current_user.role == UserRole.territory_manager and level != PositionLevel.L1.value:
        return _form_context("Territory Managers are authorized to create L1 Positions only.")

    if db.query(Position).filter(Position.code == code.upper()).first():
        return _form_context(f"Code '{code.upper()}' already exists.")
        
    err = validate_position_hierarchy(db, level, reporting_to_id)
    if err:
        return _form_context(err)

    rid = int(reporting_to_id) if (reporting_to_id and reporting_to_id.strip() != "") else None
    wid = int(warehouse_id) if (warehouse_id and warehouse_id.strip() != "") else None

    # L1 Position Warehouse Validation
    if level == PositionLevel.L1.value:
        if not wid:
            if rid:
                parent = db.query(Position).filter(Position.id == rid).first()
                if not parent or not parent.resolve_warehouse(db):
                    return _form_context("L1 Position requires a valid Warehouse assigned directly or inherited from its reporting parent hierarchy (L2/L3/L4).")
            else:
                return _form_context("L1 Position requires a valid Warehouse assigned.")

    pos = Position(name=name, code=code.upper(), level=PositionLevel(level), reporting_to_id=rid, warehouse_id=wid)
    if attached_user_id and attached_user_id.strip() != "":
        user_obj = db.query(User).filter(User.id == int(attached_user_id)).first()
        if user_obj:
            pos.users.append(user_obj)
    db.add(pos)
    db.commit()
    set_flash_success(request, f"Position '{name}' created.")
    return RedirectResponse("/master-data/positions", status_code=302)


@router.get("/{pos_id}/edit", response_class=HTMLResponse)
async def position_edit(
    pos_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
):
    item = db.query(Position).filter(Position.id == pos_id).first()
    if not item:
        set_flash_error(request, "Position not found.")
        return RedirectResponse("/master-data/positions", status_code=302)
    if current_user.role == UserRole.territory_manager and item.level != PositionLevel.L1:
        set_flash_error(request, "Territory Managers are authorized to edit L1 Positions only.")
        return RedirectResponse("/master-data/positions", status_code=302)
    managers = db.query(Position).filter(Position.is_active == True, Position.level != PositionLevel.L1, Position.id != pos_id).order_by(Position.name).all()
    beats = db.query(Beat).filter(Beat.is_active == True).order_by(Beat.name).all()
    users = db.query(User).filter(User.is_active == True, User.role != UserRole.admin).order_by(User.full_name).all()
    warehouses = db.query(Warehouse).filter(Warehouse.is_active == True).order_by(Warehouse.name).all()
    return templates.TemplateResponse("positions/form.html", {
        "request": request, "current_user": current_user,
        "item": item, "managers": managers, "beats": beats, "users": users, "warehouses": warehouses,
        "PositionLevel": PositionLevel, "error": None,
    })


@router.post("/{pos_id}/edit")
async def position_update(
    pos_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
    name: str = Form(...),
    code: str = Form(...),
    level: str = Form(...),
    reporting_to_id: Optional[str] = Form(default=None),
    warehouse_id: Optional[str] = Form(default=None),
    is_active: Optional[str] = Form(default=None),
    beat_ids: list[str] = Form(default=[]),
    attached_user_id: Optional[str] = Form(default=None),
):
    item = db.query(Position).filter(Position.id == pos_id).first()
    if not item:
        set_flash_error(request, "Position not found.")
        return RedirectResponse("/master-data/positions", status_code=302)

    def _form_context(err_msg: str):
        managers = db.query(Position).filter(Position.is_active == True, Position.level != PositionLevel.L1, Position.id != pos_id).order_by(Position.name).all()
        beats = db.query(Beat).filter(Beat.is_active == True).order_by(Beat.name).all()
        users = db.query(User).filter(User.is_active == True, User.role != UserRole.admin).order_by(User.full_name).all()
        warehouses = db.query(Warehouse).filter(Warehouse.is_active == True).order_by(Warehouse.name).all()
        return templates.TemplateResponse("positions/form.html", {
            "request": request, "current_user": current_user,
            "item": item, "managers": managers, "beats": beats, "users": users, "warehouses": warehouses,
            "PositionLevel": PositionLevel, "error": err_msg,
        })

    if current_user.role == UserRole.territory_manager and (item.level != PositionLevel.L1 or level != PositionLevel.L1.value):
        return _form_context("Territory Managers are authorized to edit L1 Positions only.")

    if db.query(Position).filter(Position.code == code.upper(), Position.id != pos_id).first():
        return _form_context(f"Code '{code.upper()}' already in use.")
        
    err = validate_position_hierarchy(db, level, reporting_to_id, current_pos_id=pos_id)
    if err:
        return _form_context(err)

    rid = int(reporting_to_id) if (reporting_to_id and reporting_to_id.strip() != "") else None
    wid = int(warehouse_id) if (warehouse_id and warehouse_id.strip() != "") else None

    # L1 Position Warehouse Validation
    if level == PositionLevel.L1.value:
        if not wid:
            if rid:
                parent = db.query(Position).filter(Position.id == rid).first()
                if not parent or not parent.resolve_warehouse(db):
                    return _form_context("L1 Position requires a valid Warehouse assigned directly or inherited from its reporting parent hierarchy (L2/L3/L4).")
            else:
                return _form_context("L1 Position requires a valid Warehouse assigned.")

    item.name = name
    item.code = code.upper()
    item.level = PositionLevel(level)
    item.reporting_to_id = rid
    item.warehouse_id = wid

    item.users.clear()
    if attached_user_id and attached_user_id.strip() != "":
        user_obj = db.query(User).filter(User.id == int(attached_user_id)).first()
        if user_obj:
            item.users.append(user_obj)
        
    db.commit()
    set_flash_success(request, f"Position '{name}' updated.")
    return RedirectResponse("/master-data/positions", status_code=302)


@router.post("/{pos_id}/activate")
async def position_activate(
    pos_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    item = db.query(Position).filter(Position.id == pos_id).first()
    if item:
        item.is_active = True
        db.commit()
        set_flash_success(request, f"'{item.name}' activated.")
    return RedirectResponse("/master-data/positions", status_code=302)


def _has_active_subordinates(position: "Position") -> bool:
    """Recursively check if any position in the entire subtree is still active."""
    for child in position.direct_reports:
        if child.is_active:
            return True
        if _has_active_subordinates(child):
            return True
    return False


@router.post("/{pos_id}/delete")
async def position_delete(
    pos_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    item = db.query(Position).filter(Position.id == pos_id).first()
    if item:
        if not item.is_vacant:
            set_flash_error(request, f"Cannot deactivate '{item.name}' because it has active assigned users.")
            return RedirectResponse("/master-data/positions", status_code=302)
        if _has_active_subordinates(item):
            set_flash_error(request, f"Cannot deactivate '{item.name}' because it has active subordinate positions.")
            return RedirectResponse("/master-data/positions", status_code=302)
        if item.beats:
            set_flash_error(request, f"Cannot deactivate '{item.name}' because it has dependent beats assigned.")
            return RedirectResponse("/master-data/positions", status_code=302)

        item.is_active = False
        db.commit()
        set_flash_success(request, f"'{item.name}' deactivated successfully.")
    return RedirectResponse("/master-data/positions", status_code=302)


@router.get("/{pos_id}/attach-beats", response_class=HTMLResponse)
async def position_attach_beats_get(
    pos_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
):
    item = db.query(Position).filter(Position.id == pos_id).first()
    if not item or not item.is_active:
        set_flash_error(request, "Active position not found.")
        return RedirectResponse("/master-data/positions", status_code=302)
    if item.level != PositionLevel.L1:
        set_flash_error(request, "Beats can only be attached to L1 positions.")
        return RedirectResponse("/master-data/positions", status_code=302)
        
    from sqlalchemy import select
    from app.models.position import position_beats
    from app.models.geography import Geography, GeoLevel

    other_mapped_beat_ids = db.scalars(
        select(position_beats.c.beat_id).where(position_beats.c.position_id != pos_id)
    ).all()

    # Filter beats matching the Region resolved from Position's Territory
    query = db.query(Beat).filter(Beat.is_active == True)
    if other_mapped_beat_ids:
        query = query.filter(~Beat.id.in_(other_mapped_beat_ids))

    territory_id = getattr(item, "territory_id", None)
    if territory_id:
        pos_territory = db.query(Geography).filter(Geography.id == territory_id).first()
        if pos_territory and pos_territory.parent_id:
            # Resolved Region ID from Territory
            resolved_region_id = pos_territory.parent_id
            # Get all territories belonging to this Region
            region_territory_ids = [t.id for t in db.query(Geography).filter(Geography.parent_id == resolved_region_id).all()]
            if region_territory_ids:
                query = query.filter(Beat.territory_id.in_(region_territory_ids))

    all_beats = query.order_by(Beat.name).all()
    assigned_beat_ids = [b.id for b in item.beats]
    territories = db.query(Geography).filter(Geography.level == GeoLevel.territory, Geography.is_active == True).order_by(Geography.name).all()

    return templates.TemplateResponse("positions/attach_beats.html", {
        "request": request,
        "current_user": current_user,
        "item": item,
        "all_beats": all_beats,
        "territories": territories,
        "assigned_beat_ids": assigned_beat_ids,
        **get_flash(request),
    })


@router.post("/{pos_id}/attach-beats")
async def position_attach_beats_post(
    pos_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
    beat_ids: list[str] = Form(default=[]),
):
    item = db.query(Position).filter(Position.id == pos_id).first()
    if not item or not item.is_active:
        set_flash_error(request, "Active position not found.")
        return RedirectResponse("/master-data/positions", status_code=302)
    if item.level != PositionLevel.L1:
        set_flash_error(request, "Beats can only be attached to L1 positions.")
        return RedirectResponse("/master-data/positions", status_code=302)
        
    item.beats.clear()
    if beat_ids:
        int_ids = [int(i) for i in beat_ids if i]
        if int_ids:
            beat_objs = db.query(Beat).filter(Beat.id.in_(int_ids)).all()
            item.beats.extend(beat_objs)
        
    db.commit()
    set_flash_success(request, f"Beats mapping updated for position '{item.name}'.")
    return RedirectResponse("/positions", status_code=302)
