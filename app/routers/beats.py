from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_web_auth, require_web_roles
from app.models.beat import Beat, BeatType, BeatGrade
from app.models.geography import Geography, GeoLevel
from app.models.user import User, UserRole
from app.utils.flash import get_flash, set_flash_error, set_flash_success
from app.utils.pagination import paginate

router = APIRouter(prefix="/beats", tags=["beats"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def beat_list(
    request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
    q: str = Query(default=""),
    beat_type: str = Query(default=""),
    page: int = Query(default=1, ge=1),
):
    query = db.query(Beat)
    if q:
        query = query.filter(Beat.name.ilike(f"%{q}%") | Beat.code.ilike(f"%{q}%"))
    if beat_type and beat_type in [bt.value for bt in BeatType]:
        query = query.filter(Beat.beat_type == beat_type)
    query = query.order_by(Beat.name)
    pagination = paginate(query, page)
    return templates.TemplateResponse("beats/list.html", {
        "request": request, "current_user": current_user,
        "pagination": pagination, "q": q, "beat_type": beat_type,
        "BeatType": BeatType, **get_flash(request),
    })


@router.get("/new", response_class=HTMLResponse)
async def beat_new(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
):
    territories = db.query(Geography).filter(
        Geography.level == GeoLevel.territory, Geography.is_active == True
    ).order_by(Geography.name).all()
    return templates.TemplateResponse("beats/form.html", {
        "request": request, "current_user": current_user,
        "item": None, "territories": territories, "BeatType": BeatType, "BeatGrade": BeatGrade, "error": None,
    })


@router.post("/new")
async def beat_create(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
    name: str = Form(...),
    code: str = Form(...),
    beat_type: str = Form(...),
    beat_grade: Optional[str] = Form(default=None),
    territory_id: Optional[str] = Form(default=None),
    erp_id: Optional[str] = Form(default=None),
):
    if db.query(Beat).filter(Beat.code == code.upper()).first():
        territories = db.query(Geography).filter(Geography.level == GeoLevel.territory, Geography.is_active == True).order_by(Geography.name).all()
        return templates.TemplateResponse("beats/form.html", {
            "request": request, "current_user": current_user,
            "item": None, "territories": territories, "BeatType": BeatType, "BeatGrade": BeatGrade,
            "error": f"Code '{code.upper()}' already exists.",
        })
    db.add(Beat(
        name=name, code=code.upper(), beat_type=BeatType(beat_type),
        beat_grade=BeatGrade(beat_grade) if beat_grade else None,
        territory_id=int(territory_id) if territory_id else None,
        erp_id=erp_id or None,
    ))
    db.commit()
    set_flash_success(request, f"Beat '{name}' created.")
    return RedirectResponse("/beats", status_code=302)


@router.get("/{beat_id}/edit", response_class=HTMLResponse)
async def beat_edit(
    beat_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
):
    item = db.query(Beat).filter(Beat.id == beat_id).first()
    if not item or not item.is_active:
        set_flash_error(request, "Active beat not found or beat is inactive.")
        return RedirectResponse("/beats", status_code=302)
    territories = db.query(Geography).filter(Geography.level == GeoLevel.territory, Geography.is_active == True).order_by(Geography.name).all()
    return templates.TemplateResponse("beats/form.html", {
        "request": request, "current_user": current_user,
        "item": item, "territories": territories, "BeatType": BeatType, "BeatGrade": BeatGrade, "error": None,
    })


@router.post("/{beat_id}/edit")
async def beat_update(
    beat_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
    name: str = Form(...),
    code: str = Form(...),
    beat_type: str = Form(...),
    beat_grade: Optional[str] = Form(default=None),
    territory_id: Optional[str] = Form(default=None),
    erp_id: Optional[str] = Form(default=None),
):
    item = db.query(Beat).filter(Beat.id == beat_id).first()
    if not item or not item.is_active:
        set_flash_error(request, "Active beat not found or beat is inactive.")
        return RedirectResponse("/beats", status_code=302)
    if db.query(Beat).filter(Beat.code == code.upper(), Beat.id != beat_id).first():
        territories = db.query(Geography).filter(Geography.level == GeoLevel.territory, Geography.is_active == True).order_by(Geography.name).all()
        return templates.TemplateResponse("beats/form.html", {
            "request": request, "current_user": current_user,
            "item": item, "territories": territories, "BeatType": BeatType, "BeatGrade": BeatGrade,
            "error": f"Code '{code.upper()}' already in use.",
        })
    item.name = name
    item.code = code.upper()
    item.beat_type = BeatType(beat_type)
    item.beat_grade = BeatGrade(beat_grade) if beat_grade else None
    item.territory_id = int(territory_id) if territory_id else None
    item.erp_id = erp_id or None
    db.commit()
    set_flash_success(request, f"Beat '{name}' updated.")
    return RedirectResponse("/beats", status_code=302)


@router.post("/{beat_id}/activate")
async def beat_activate(
    beat_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
):
    item = db.query(Beat).filter(Beat.id == beat_id).first()
    if item:
        item.is_active = True
        db.commit()
        set_flash_success(request, f"'{item.name}' activated.")
    return RedirectResponse("/beats", status_code=302)


@router.post("/{beat_id}/delete")
async def beat_delete(
    beat_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
):
    item = db.query(Beat).filter(Beat.id == beat_id).first()
    if item:
        if item.active_outlet_count > 0:
            set_flash_error(request, f"Cannot deactivate '{item.name}' because it has active outlets.")
            return RedirectResponse("/beats", status_code=302)
        if any(p.is_active for p in item.positions):
            set_flash_error(request, f"Cannot deactivate '{item.name}' because it is attached to active positions.")
            return RedirectResponse("/beats", status_code=302)
            
        item.is_active = False
        db.commit()
        set_flash_success(request, f"'{item.name}' deactivated.")
    return RedirectResponse("/beats", status_code=302)
