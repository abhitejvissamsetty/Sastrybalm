from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_web_roles
from app.models.company import CompanyProfile
from app.models.geography import Geography, GeoLevel
from app.models.position import Position
from app.models.user import ModuleName, PaymentMode, User, UserModuleAccess, UserRole
from app.utils.flash import get_flash, set_flash_error, set_flash_success
from app.utils.pagination import paginate
from app.utils.security import hash_password

router = APIRouter(prefix="/users", tags=["users"])
templates = Jinja2Templates(directory="app/templates")


def _form_context(db: Session, for_role: str = "") -> dict:
    positions_query = db.query(Position).filter(Position.is_active == True)
    if for_role == UserRole.field_rep.value:
        # Filter positions for field reps to L1 level
        positions_query = positions_query.filter(Position.level == "L1")
    return {
        "positions": positions_query.order_by(Position.name).all(),
        "UserRole": UserRole,
        "ModuleName": ModuleName,
        "PaymentMode": PaymentMode,
    }


@router.get("/role-matrix", response_class=HTMLResponse)
async def user_role_matrix(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
):
    """Render Admin Role & Access Permissions Matrix."""
    return templates.TemplateResponse("users/role_matrix.html", {
        "request": request,
        "current_user": current_user,
        "UserRole": UserRole,
        **get_flash(request),
    })


@router.get("/{user_id}/position-view", response_class=HTMLResponse)
async def user_position_view(
    user_id: int,
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
):
    """View and update user position assignment & hierarchy tree."""
    user_obj = db.query(User).filter(User.id == user_id).first()
    if not user_obj:
        set_flash_error(request, "User not found.")
        return RedirectResponse("/users", status_code=302)

    pos_query = db.query(Position).filter(Position.is_active == True)
    if user_obj.role == UserRole.field_rep:
        # Filter available positions for field reps to L1 level
        pos_query = pos_query.filter(Position.level == "L1")

    all_positions = pos_query.order_by(Position.name).all()
    assigned_ids = [p.id for p in user_obj.positions]

    return templates.TemplateResponse("users/position_view_modal.html", {
        "request": request,
        "current_user": current_user,
        "user_obj": user_obj,
        "all_positions": all_positions,
        "assigned_ids": assigned_ids,
        **get_flash(request),
    })


@router.post("/{user_id}/position-view")
async def user_position_update(
    user_id: int,
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
    position_ids: list[str] = Form(default=[]),
):
    """Update assigned positions for user."""
    user_obj = db.query(User).filter(User.id == user_id).first()
    if not user_obj:
        set_flash_error(request, "User not found.")
        return RedirectResponse("/users", status_code=302)

    user_obj.positions.clear()
    if position_ids:
        pos_objs = db.query(Position).filter(Position.id.in_(position_ids)).all()
        user_obj.positions.extend(pos_objs)

    db.commit()
    set_flash_success(request, f"Position assignments updated for '{user_obj.full_name}'.")
    return RedirectResponse(f"/users/{user_id}/position-view", status_code=302)



@router.get("", response_class=HTMLResponse)
async def user_list(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
    q: str = Query(default=""),
    role: str = Query(default=""),
    page: int = Query(default=1, ge=1),
):
    query = db.query(User)
    if q:
        query = query.filter(
            User.full_name.ilike(f"%{q}%") | User.username.ilike(f"%{q}%") | User.email.ilike(f"%{q}%")
        )
    if role and role in [r.value for r in UserRole]:
        query = query.filter(User.role == role)
    query = query.order_by(User.full_name)
    pagination = paginate(query, page)
    return templates.TemplateResponse("users/list.html", {
        "request": request, "current_user": current_user,
        "pagination": pagination, "q": q, "role": role,
        "UserRole": UserRole, **get_flash(request),
    })


@router.get("/new", response_class=HTMLResponse)
async def user_new(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    return templates.TemplateResponse("users/form.html", {
        "request": request, "current_user": current_user,
        "item": None, "error": None, **_form_context(db),
    })


@router.post("/new")
async def user_create(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
    full_name: str = Form(...),
    email: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    employee_id: Optional[str] = Form(default=None),
    phone: str = Form(...),
    position_ids: list[str] = Form(default=[]),
    company_profile_id: Optional[str] = Form(default=None),
    modules: list[str] = Form(default=[]),
):
    import re
    err = None
    phone_clean = phone.strip() if phone else ""
    if not phone_clean:
        err = "Phone number is mandatory."
    elif not re.match(r"^\d{10}$", phone_clean):
        err = "Phone number must be exactly 10 digits."
    elif db.query(User).filter(User.phone == phone_clean).first():
        err = f"Phone number '{phone_clean}' already registered."
    elif role == UserRole.admin.value and db.query(User).filter(User.role == UserRole.admin).first():
        err = "Only one System Administrator is permitted for this software setup. Admin credentials are configured in .env."
    elif db.query(User).filter(User.email == email).first():
        err = f"Email '{email}' already registered."
    elif db.query(User).filter(User.username == username).first():
        err = f"Username '{username}' already taken."
        
    if err:
        return templates.TemplateResponse("users/form.html", {
            "request": request, "current_user": current_user,
            "item": None, "error": err, **_form_context(db),
        })
        
    user = User(
        full_name=full_name, email=email, username=username,
        hashed_password=hash_password(password),
        role=UserRole(role),
        employee_id=employee_id or None, phone=phone_clean or None,
        company_profile_id=int(company_profile_id) if company_profile_id else None,
        payment_mode=None,
        denomination_mandatory=False,
    )
    if position_ids:
        pos_objs = db.query(Position).filter(Position.id.in_(position_ids)).all()
        user.positions.extend(pos_objs)
    db.add(user)
    db.flush()
    
    # Save module access
    for mod in modules:
        if mod in [m.value for m in ModuleName]:
            db.add(UserModuleAccess(user_id=user.id, module=ModuleName(mod), is_active=True))
            
    db.commit()
    set_flash_success(request, f"User '{full_name}' created.")
    return RedirectResponse("/users", status_code=302)


@router.get("/{user_id}/edit", response_class=HTMLResponse)
async def user_edit(
    user_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    item = db.query(User).filter(User.id == user_id).first()
    if not item:
        set_flash_error(request, "User not found.")
        return RedirectResponse("/users", status_code=302)
    return templates.TemplateResponse("users/form.html", {
        "request": request, "current_user": current_user,
        "item": item, "error": None, **_form_context(db),
    })


@router.post("/{user_id}/edit")
async def user_update(
    user_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
    full_name: str = Form(...),
    email: str = Form(...),
    role: str = Form(...),
    employee_id: Optional[str] = Form(default=None),
    phone: str = Form(...),
    position_ids: list[str] = Form(default=[]),
    company_profile_id: Optional[str] = Form(default=None),
    is_active: Optional[str] = Form(default=None),
    new_password: Optional[str] = Form(default=None),
    modules: list[str] = Form(default=[]),
):
    item = db.query(User).filter(User.id == user_id).first()
    if not item:
        set_flash_error(request, "User not found.")
        return RedirectResponse("/users", status_code=302)
        
    import re
    err = None
    phone_clean = phone.strip() if phone else ""
    if not phone_clean:
        err = "Phone number is mandatory."
    elif not re.match(r"^\d{10}$", phone_clean):
        err = "Phone number must be exactly 10 digits."
    elif db.query(User).filter(User.email == email, User.id != user_id).first():
        err = f"Email '{email}' already registered."
        
    if err:
        return templates.TemplateResponse("users/form.html", {
            "request": request, "current_user": current_user,
            "item": item, "error": err, **_form_context(db),
        })
        
    item.full_name = full_name
    item.email = email
    item.role = UserRole(role)
    item.employee_id = employee_id or None
    item.phone = phone_clean
    item.company_profile_id = int(company_profile_id) if company_profile_id else None
    item.is_active = is_active == "on"
    if new_password:
        item.hashed_password = hash_password(new_password)

    item.positions.clear()
    if position_ids:
        pos_objs = db.query(Position).filter(Position.id.in_(position_ids)).all()
        item.positions.extend(pos_objs)

    # Refresh module access — flush first to clear session state before re-inserting
    db.query(UserModuleAccess).filter(UserModuleAccess.user_id == user_id).delete(synchronize_session='fetch')
    db.flush()
    for mod in modules:
        if mod in [m.value for m in ModuleName]:
            db.add(UserModuleAccess(user_id=user_id, module=ModuleName(mod), is_active=True))

    db.commit()
    set_flash_success(request, f"User '{full_name}' updated.")
    return RedirectResponse("/users", status_code=302)


@router.post("/{user_id}/delete")
async def user_deactivate(
    user_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    if user_id == current_user.id:
        set_flash_error(request, "You cannot deactivate your own account.")
        return RedirectResponse("/users", status_code=302)
    item = db.query(User).filter(User.id == user_id).first()
    if item:
        item.is_active = False
        db.commit()
        set_flash_success(request, f"'{item.full_name}' deactivated.")
    return RedirectResponse("/users", status_code=302)


@router.post("/{user_id}/activate")
async def user_activate(
    user_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    item = db.query(User).filter(User.id == user_id).first()
    if item:
        item.is_active = True
        db.commit()
        set_flash_success(request, f"'{item.full_name}' activated.")
    return RedirectResponse("/users", status_code=302)


@router.post("/{user_id}/activation-code")
async def user_activation_code(
    user_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    import random
    item = db.query(User).filter(User.id == user_id).first()
    if not item:
        set_flash_error(request, "User not found.")
        return RedirectResponse("/users", status_code=302)
        
    code = "".join([str(random.randint(0, 9)) for _ in range(6)])
    item.activation_code = code
    db.commit()
    set_flash_success(request, f"Activation code generated for {item.full_name}: {code}")
    return RedirectResponse("/users", status_code=302)


@router.post("/{user_id}/register")
async def user_register(
    user_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    item = db.query(User).filter(User.id == user_id).first()
    if not item:
        set_flash_error(request, "User not found.")
        return RedirectResponse("/users", status_code=302)
        
    item.is_registered = True
    db.commit()
    set_flash_success(request, f"User '{item.full_name}' registered successfully.")
    return RedirectResponse("/users", status_code=302)
