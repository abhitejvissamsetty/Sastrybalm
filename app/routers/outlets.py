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

router = APIRouter(prefix="/master-data/outlets", tags=["outlets"])
templates = Jinja2Templates(directory="app/templates")


from app.utils.geography_scope import get_user_allowed_geography_ids
from app.models.outlet_version import OutletVersion
import json


def _snapshot_outlet_version(db: Session, outlet: Outlet, user_id: Optional[int], summary: str) -> OutletVersion:
    from sqlalchemy import func
    max_ver = db.query(func.max(OutletVersion.version_number)).filter(OutletVersion.outlet_id == outlet.id).scalar() or 0
    version = OutletVersion(
        outlet_id=outlet.id,
        version_number=max_ver + 1,
        name=outlet.name,
        code=outlet.code,
        owner_name=outlet.owner_name,
        mobile=outlet.mobile,
        address=outlet.address,
        pincode=outlet.pincode,
        gstin=outlet.gstin,
        channel=outlet.channel.value if outlet.channel else None,
        shop_type=outlet.shop_type.value if outlet.shop_type else None,
        beat_id=outlet.beat_id,
        territory_id=outlet.territory_id,
        gps_lat=outlet.gps_lat,
        gps_lng=outlet.gps_lng,
        photo_url=outlet.photo_url,
        status=outlet.status.value if outlet.status else None,
        changed_by_id=user_id,
        change_summary=summary,
    )
    db.add(version)
    db.commit()
    return version


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
    allowed_geo_ids = get_user_allowed_geography_ids(current_user, db)
    if allowed_geo_ids is not None:
        query = query.filter(Outlet.territory_id.in_(allowed_geo_ids))

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
    beats_query = db.query(Beat).filter(Beat.is_active == True)
    if allowed_geo_ids is not None:
        beats_query = beats_query.filter(Beat.territory_id.in_(allowed_geo_ids))
    beats = beats_query.order_by(Beat.name).all()
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
    photo: Optional[UploadFile] = File(default=None),
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

    photo_url = None
    if photo and photo.filename:
        file_bytes = await photo.read()
        if file_bytes:
            from app.utils.s3_service import upload_image_file
            photo_url = upload_image_file(
                db=db,
                file_bytes=file_bytes,
                original_filename=photo.filename,
                folder_prefix="outlets",
                content_type=photo.content_type or "image/jpeg",
                bucket_type="permanent",
            )

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
        photo_url=photo_url,
        status=OutletStatus.active,
    )
    db.add(outlet)
    db.commit()
    set_flash_success(request, f"Outlet '{name}' created successfully.")
    return RedirectResponse("/master-data/outlets", status_code=302)


@router.get("/{outlet_id}", response_class=HTMLResponse)
async def outlet_detail(
    outlet_id: int, request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
):
    item = db.query(Outlet).filter(Outlet.id == outlet_id).first()
    if not item:
        set_flash_error(request, "Outlet not found.")
        return RedirectResponse("/master-data/outlets", status_code=302)
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
        return RedirectResponse("/master-data/outlets", status_code=302)
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
    photo: Optional[UploadFile] = File(default=None),
):
    item = db.query(Outlet).filter(Outlet.id == outlet_id).first()
    if not item:
        set_flash_error(request, "Outlet not found.")
        return RedirectResponse("/master-data/outlets", status_code=302)

    allowed_geo_ids = get_user_allowed_geography_ids(current_user, db)
    if allowed_geo_ids is not None:
        if item.territory_id and item.territory_id not in allowed_geo_ids:
            set_flash_error(request, "Access denied. You can only edit outlets in your assigned geography.")
            return RedirectResponse("/master-data/outlets", status_code=302)

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

    # Upload new photo if provided
    if photo and photo.filename:
        file_bytes = await photo.read()
        if file_bytes:
            from app.utils.s3_service import upload_image_file
            item.photo_url = upload_image_file(
                db=db,
                file_bytes=file_bytes,
                original_filename=photo.filename,
                folder_prefix="outlets",
                content_type=photo.content_type or "image/jpeg",
                bucket_type="permanent",
            )

    # Non-admin edit creates approval request
    if current_user.role != UserRole.admin:
        from app.models.auto_flag import AutoFlag, FlagType, FlagSeverity, FlagStatus
        proposed_payload = json.dumps({
            "name": name, "code": code.upper() if code else None, "owner_name": owner_name,
            "mobile": mobile, "address": address, "channel": channel, "shop_type": shop_type,
            "gstin": gstin, "pincode": pincode, "beat_id": int(beat_id) if beat_id else None,
            "territory_id": int(territory_id) if territory_id else None,
            "gps_lat": float(gps_lat) if gps_lat else None, "gps_lng": float(gps_lng) if gps_lng else None
        })
        flag = AutoFlag(
            flag_type=FlagType.unusual_activity,
            severity=FlagSeverity.medium,
            status=FlagStatus.open,
            user_id=current_user.id,
            entity_type="outlet_edit_approval",
            entity_id=item.id,
            title=f"Pending Outlet Edit Approval: {item.name}",
            description=f"User {current_user.full_name} submitted edit for outlet '{item.name}'. Proposed changes: {proposed_payload}",
        )
        db.add(flag)
        db.commit()
        set_flash_success(request, f"Changes to outlet '{item.name}' submitted for Admin approval.")
        return RedirectResponse(f"/master-data/outlets/{outlet_id}", status_code=302)

    # Admin direct edit — Snapshot current state first
    _snapshot_outlet_version(db, item, current_user.id, f"Edited by Admin {current_user.full_name}")

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
    set_flash_success(request, f"Outlet '{name}' updated and version snapshot saved.")
    return RedirectResponse(f"/master-data/outlets/{outlet_id}", status_code=302)


@router.get("/{outlet_id}/history", response_class=HTMLResponse)
async def outlet_history(
    outlet_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    item = db.query(Outlet).filter(Outlet.id == outlet_id).first()
    if not item:
        set_flash_error(request, "Outlet not found.")
        return RedirectResponse("/master-data/outlets", status_code=302)
    versions = db.query(OutletVersion).filter(OutletVersion.outlet_id == outlet_id).order_by(OutletVersion.version_number.desc()).all()
    return templates.TemplateResponse("outlets/history.html", {
        "request": request, "current_user": current_user,
        "item": item, "versions": versions, **get_flash(request),
    })


@router.post("/{outlet_id}/revert/{version_id}")
async def outlet_revert(
    outlet_id: int, version_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    item = db.query(Outlet).filter(Outlet.id == outlet_id).first()
    ver = db.query(OutletVersion).filter(OutletVersion.id == version_id, OutletVersion.outlet_id == outlet_id).first()
    if not item or not ver:
        set_flash_error(request, "Version snapshot not found.")
        return RedirectResponse(f"/master-data/outlets/{outlet_id}", status_code=302)

    # Snapshot current state before reverting
    _snapshot_outlet_version(db, item, current_user.id, f"Reverted back to Version #{ver.version_number} by Admin {current_user.full_name}")

    item.name = ver.name
    item.code = ver.code
    item.owner_name = ver.owner_name
    item.mobile = ver.mobile
    item.address = ver.address
    item.pincode = ver.pincode
    item.gstin = ver.gstin
    item.channel = ChannelType(ver.channel) if ver.channel else None
    item.shop_type = ShopType(ver.shop_type) if ver.shop_type else None
    item.beat_id = ver.beat_id
    item.territory_id = ver.territory_id
    item.gps_lat = ver.gps_lat
    item.gps_lng = ver.gps_lng
    if ver.status:
        try:
            item.status = OutletStatus(ver.status)
        except ValueError:
            pass
    db.commit()
    set_flash_success(request, f"Outlet '{item.name}' successfully reverted to Version #{ver.version_number}.")
    return RedirectResponse(f"/master-data/outlets/{outlet_id}", status_code=302)


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
    return RedirectResponse("/master-data/outlets", status_code=302)


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
    return RedirectResponse("/master-data/outlets", status_code=302)


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
