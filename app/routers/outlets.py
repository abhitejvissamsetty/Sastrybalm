import csv
import io
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_web_auth, require_web_roles
from app.models.beat import Beat
from app.models.geography import Geography, GeoLevel
from app.models.outlet import Outlet, OutletStatus, ChannelType, ShopType
from app.models.user import User, UserRole
from app.utils.csv_import import parse_csv_bytes
from app.utils.flash import get_flash, set_flash_error, set_flash_success
from app.utils.pagination import paginate

router = APIRouter(prefix="/outlets", tags=["outlets"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def outlet_list(
    request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
    q: str = Query(default=""),
    status: str = Query(default=""),
    beat_id: str = Query(default=""),
    page: int = Query(default=1, ge=1),
):
    query = db.query(Outlet)
    if q:
        query = query.filter(Outlet.name.ilike(f"%{q}%") | Outlet.mobile.ilike(f"%{q}%") | Outlet.code.ilike(f"%{q}%"))
    if status and status in [s.value for s in OutletStatus]:
        query = query.filter(Outlet.status == status)
    if beat_id:
        query = query.filter(Outlet.beat_id == int(beat_id))
    selected_beat = None
    if beat_id:
        try:
            selected_beat = db.query(Beat).filter(Beat.id == int(beat_id)).first()
        except ValueError:
            pass
    query = query.order_by(Outlet.name)
    pagination = paginate(query, page)
    beats = db.query(Beat).filter(Beat.is_active == True).order_by(Beat.name).all()
    return templates.TemplateResponse("outlets/list.html", {
        "request": request, "current_user": current_user,
        "pagination": pagination, "q": q, "status": status, "beat_id": beat_id,
        "selected_beat": selected_beat,
        "beats": beats, "OutletStatus": OutletStatus, **get_flash(request),
    })


from app.utils.beat_types import get_all_beat_types

@router.get("/new", response_class=HTMLResponse)
async def outlet_new(
    request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
):
    beats = db.query(Beat).filter(Beat.is_active == True).order_by(Beat.name).all()
    territories = db.query(Geography).filter(Geography.level == GeoLevel.territory, Geography.is_active == True).order_by(Geography.name).all()
    return templates.TemplateResponse("outlets/form.html", {
        "request": request, "current_user": current_user,
        "item": None, "beats": beats, "territories": territories, "error": None,
        "beat_types": get_all_beat_types(db), "ChannelType": ChannelType, "ShopType": ShopType,
    })


@router.post("/new")
async def outlet_create(
    request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
    name: str = Form(...),
    code: Optional[str] = Form(default=None),
    owner_name: Optional[str] = Form(default=None),
    mobile: Optional[str] = Form(default=None),
    address: Optional[str] = Form(default=None),
    channel: Optional[str] = Form(default=None),
    shop_type: Optional[str] = Form(default=None),
    external_id: Optional[str] = Form(default=None),
    gstin: Optional[str] = Form(default=None),
    pincode: Optional[str] = Form(default=None),
    beat_id: Optional[str] = Form(default=None),
    territory_id: Optional[str] = Form(default=None),
    gps_lat: Optional[str] = Form(default=None),
    gps_lng: Optional[str] = Form(default=None),
):
    beats = db.query(Beat).filter(Beat.is_active == True).order_by(Beat.name).all()
    territories = db.query(Geography).filter(Geography.level == GeoLevel.territory, Geography.is_active == True).order_by(Geography.name).all()

    # Generate code if blank
    if not code or not code.strip():
        last_outlet = db.query(Outlet).order_by(Outlet.id.desc()).first()
        next_id = (last_outlet.id + 1) if last_outlet else 1
        code = f"OUT{next_id:04d}"
        while db.query(Outlet).filter(Outlet.code == code).first():
            next_id += 1
            code = f"OUT{next_id:04d}"

    # Unique code check
    if code and db.query(Outlet).filter(Outlet.code == code.upper()).first():
        return templates.TemplateResponse("outlets/form.html", {
            "request": request, "current_user": current_user,
            "item": None, "beats": beats, "territories": territories,
            "ChannelType": ChannelType, "ShopType": ShopType,
            "error": f"Code '{code.upper()}' already exists.",
        })

    # Unique mobile check
    if mobile and mobile.strip():
        existing_mobile = db.query(Outlet).filter(Outlet.mobile == mobile.strip()).first()
        if existing_mobile:
            return templates.TemplateResponse("outlets/form.html", {
                "request": request, "current_user": current_user,
                "item": None, "beats": beats, "territories": territories,
                "ChannelType": ChannelType, "ShopType": ShopType,
                "error": f"Mobile number '{mobile.strip()}' is already in use by another outlet.",
            })

    # Active outlet requires a Beat
    if not beat_id or beat_id.strip() == "":
        return templates.TemplateResponse("outlets/form.html", {
            "request": request, "current_user": current_user,
            "item": None, "beats": beats, "territories": territories,
            "ChannelType": ChannelType, "ShopType": ShopType,
            "error": "Beat is mandatory for active outlets.",
        })

    outlet = Outlet(
        name=name,
        code=code.upper() if code else None,
        owner_name=owner_name or None,
        mobile=mobile or None,
        address=address or None,
        channel=ChannelType(channel) if channel else None,
        shop_type=ShopType(shop_type) if shop_type else None,
        external_id=external_id or None,
        gstin=gstin or None,
        pincode=pincode or None,
        beat_id=int(beat_id) if beat_id else None,
        territory_id=int(territory_id) if territory_id else None,
        gps_lat=float(gps_lat) if gps_lat else None,
        gps_lng=float(gps_lng) if gps_lng else None,
        status=OutletStatus.active,
    )
    db.add(outlet)
    db.commit()
    set_flash_success(request, f"Outlet '{name}' created successfully.")
    return RedirectResponse("/outlets", status_code=302)


@router.get("/{outlet_id}", response_class=HTMLResponse)
async def outlet_detail(
    outlet_id: int, request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
):
    item = db.query(Outlet).filter(Outlet.id == outlet_id).first()
    if not item:
        set_flash_error(request, "Outlet not found.")
        return RedirectResponse("/outlets", status_code=302)
    from app.models.order import Order, OrderStatus
    from app.models.timesheet import VisitRecord
    recent_orders = (
        db.query(Order).filter(Order.outlet_id == outlet_id)
        .order_by(Order.order_date.desc()).limit(10).all()
    )
    recent_visits = (
        db.query(VisitRecord).filter(VisitRecord.outlet_id == outlet_id)
        .order_by(VisitRecord.visit_time.desc()).limit(10).all()
    )
    return templates.TemplateResponse("outlets/detail.html", {
        "request": request, "current_user": current_user,
        "item": item, "recent_orders": recent_orders, "recent_visits": recent_visits,
    })


@router.get("/{outlet_id}/edit", response_class=HTMLResponse)
async def outlet_edit(
    outlet_id: int, request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
):
    item = db.query(Outlet).filter(Outlet.id == outlet_id).first()
    if not item:
        set_flash_error(request, "Outlet not found.")
        return RedirectResponse("/outlets", status_code=302)
    beats = db.query(Beat).filter(Beat.is_active == True).order_by(Beat.name).all()
    territories = db.query(Geography).filter(Geography.level == GeoLevel.territory, Geography.is_active == True).order_by(Geography.name).all()
    return templates.TemplateResponse("outlets/form.html", {
        "request": request, "current_user": current_user,
        "item": item, "beats": beats, "territories": territories, "error": None,
        "beat_types": get_all_beat_types(db), "ChannelType": ChannelType, "ShopType": ShopType,
    })


@router.post("/{outlet_id}/edit")
async def outlet_update(
    outlet_id: int, request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
    name: str = Form(...),
    code: Optional[str] = Form(default=None),
    owner_name: Optional[str] = Form(default=None),
    mobile: Optional[str] = Form(default=None),
    address: Optional[str] = Form(default=None),
    channel: Optional[str] = Form(default=None),
    shop_type: Optional[str] = Form(default=None),
    external_id: Optional[str] = Form(default=None),
    gstin: Optional[str] = Form(default=None),
    pincode: Optional[str] = Form(default=None),
    beat_id: Optional[str] = Form(default=None),
    territory_id: Optional[str] = Form(default=None),
    gps_lat: Optional[str] = Form(default=None),
    gps_lng: Optional[str] = Form(default=None),
):
    item = db.query(Outlet).filter(Outlet.id == outlet_id).first()
    if not item:
        set_flash_error(request, "Outlet not found.")
        return RedirectResponse("/outlets", status_code=302)

    beats = db.query(Beat).filter(Beat.is_active == True).order_by(Beat.name).all()
    territories = db.query(Geography).filter(Geography.level == GeoLevel.territory, Geography.is_active == True).order_by(Geography.name).all()

    # Unique code check
    if code and db.query(Outlet).filter(Outlet.code == code.upper(), Outlet.id != outlet_id).first():
        return templates.TemplateResponse("outlets/form.html", {
            "request": request, "current_user": current_user,
            "item": item, "beats": beats, "territories": territories,
            "ChannelType": ChannelType, "ShopType": ShopType,
            "error": f"Code '{code.upper()}' already in use.",
        })

    # Unique mobile check
    if mobile and mobile.strip():
        existing_mobile = db.query(Outlet).filter(Outlet.mobile == mobile.strip(), Outlet.id != outlet_id).first()
        if existing_mobile:
            return templates.TemplateResponse("outlets/form.html", {
                "request": request, "current_user": current_user,
                "item": item, "beats": beats, "territories": territories,
                "ChannelType": ChannelType, "ShopType": ShopType,
                "error": f"Mobile number '{mobile.strip()}' is already in use by another outlet.",
            })

    # Active outlet requires a Beat
    if item.status == OutletStatus.active and (not beat_id or beat_id.strip() == ""):
        return templates.TemplateResponse("outlets/form.html", {
            "request": request, "current_user": current_user,
            "item": item, "beats": beats, "territories": territories,
            "ChannelType": ChannelType, "ShopType": ShopType,
            "error": "Beat is mandatory for active outlets.",
        })

    item.name = name
    item.code = code.upper() if code else None
    item.owner_name = owner_name or None
    item.mobile = mobile or None
    item.address = address or None
    item.channel = ChannelType(channel) if channel else None
    item.shop_type = ShopType(shop_type) if shop_type else None
    item.external_id = external_id or None
    item.gstin = gstin or None
    item.pincode = pincode or None
    item.beat_id = int(beat_id) if beat_id else None
    item.territory_id = int(territory_id) if territory_id else None
    item.gps_lat = float(gps_lat) if gps_lat else None
    item.gps_lng = float(gps_lng) if gps_lng else None
    db.commit()
    set_flash_success(request, f"Outlet '{name}' updated.")
    return RedirectResponse("/outlets", status_code=302)


@router.post("/{outlet_id}/toggle")
async def outlet_toggle(
    outlet_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
):
    item = db.query(Outlet).filter(Outlet.id == outlet_id).first()
    if item:
        if item.status == OutletStatus.active:
            item.status = OutletStatus.inactive
            set_flash_success(request, f"'{item.name}' deactivated.")
        else:
            item.status = OutletStatus.active
            set_flash_success(request, f"'{item.name}' activated.")
        db.commit()
    return RedirectResponse("/outlets", status_code=302)


@router.post("/import")
async def outlet_import(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
):
    """
    CSV format: name, code, mobile, beat_code, address, gps_lat, gps_lng, channel
    """
    content = await file.read()
    rows = parse_csv_bytes(content)
    created = 0
    errors: list[str] = []
    for i, row in enumerate(rows, start=2):
        name = row.get("name", "").strip()
        if not name:
            errors.append(f"Row {i}: missing name")
            continue
        code = row.get("code", "").upper() or None
        if code and db.query(Outlet).filter(Outlet.code == code).first():
            errors.append(f"Row {i}: code '{code}' already exists")
            continue
        beat_code = row.get("beat_code", "").upper()
        beat = db.query(Beat).filter(Beat.code == beat_code).first() if beat_code else None
        try:
            lat = float(row["gps_lat"]) if row.get("gps_lat") else None
            lng = float(row["gps_lng"]) if row.get("gps_lng") else None
        except ValueError:
            lat = lng = None
        db.add(Outlet(
            name=name, code=code, mobile=row.get("mobile") or None,
            beat_id=beat.id if beat else None, address=row.get("address") or None,
            gps_lat=lat, gps_lng=lng, channel=row.get("channel") or None,
            status=OutletStatus.active,
        ))
        created += 1
    db.commit()
    msg = f"Imported {created} outlets."
    if errors:
        msg += f" {len(errors)} row(s) skipped: " + "; ".join(errors[:3])
        set_flash_error(request, msg)
    else:
        set_flash_success(request, msg)
    return RedirectResponse("/outlets", status_code=302)


@router.get("/export")
async def outlet_export(
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
):
    outlets = db.query(Outlet).order_by(Outlet.name).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "name", "code", "mobile", "beat", "territory", "address", "gps_lat", "gps_lng", "channel", "status"])
    for o in outlets:
        writer.writerow([
            o.id, o.name, o.code or "", o.mobile or "",
            o.beat.name if o.beat else "", o.territory.name if o.territory else "",
            o.address or "", o.gps_lat or "", o.gps_lng or "",
            o.channel or "", o.status.value,
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=outlets.csv"},
    )
