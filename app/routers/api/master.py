from typing import List, Optional

from fastapi import APIRouter, Depends, Query, HTTPException, File, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload

from app.dependencies import get_db, require_api_auth, require_restricted_module_api_access
from app.models.beat import Beat, BeatType, BeatGrade
from app.models.company import SystemConfiguration
from app.models.geography import Geography
from app.models.outlet import Outlet, OutletStatus, ChannelType, ShopType
from app.models.position import Position
from app.models.product import Product
from app.models.user import User
from app.services.access_control import (
    build_access_scope,
    require_beat_access,
    require_outlet_access,
    scope_outlet_query,
)

router = APIRouter(prefix="/api/v1", tags=["mobile-master"])


@router.get("/geography/tree")
async def geography_tree(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    """Full active geography tree for mobile offline cache."""
    def _node(geo: Geography) -> dict:
        return {
            "id": geo.id,
            "name": geo.name,
            "code": geo.code,
            "level": geo.level.value,
            "erp_id": geo.erp_id,
            "children": [_node(c) for c in geo.children if c.is_active],
        }

    scope = build_access_scope(current_user, db)
    roots_query = db.query(Geography).filter(Geography.is_active == True)
    if scope.unrestricted:
        roots_query = roots_query.filter(Geography.parent_id == None)
    else:
        roots_query = roots_query.filter(
            Geography.id.in_(scope.geography_ids or {-1})
        )
    total = roots_query.count()
    roots = roots_query.order_by(Geography.name).offset(
        (page - 1) * per_page
    ).limit(per_page).all()
    return {
        "page": page,
        "per_page": per_page,
        "total": total,
        "tree": [_node(g) for g in roots],
    }


@router.get("/beats/daily-plan")
async def beat_daily_plan(
    beat_id: int = Query(...),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=100, ge=1, le=200),
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    """Ordered outlet list for a beat (approved outlets only)."""
    beat = require_beat_access(db, current_user, beat_id, active_only=True)

    outlet_query = (
        db.query(Outlet)
        .filter(Outlet.beat_id == beat_id, Outlet.status == OutletStatus.active)
        .order_by(Outlet.name)
    )
    total = outlet_query.count()
    outlets = outlet_query.offset((page - 1) * per_page).limit(per_page).all()
    return {
        "beat": {
            "id": beat.id,
            "name": beat.name,
            "code": beat.code,
            "beat_type": beat.beat_type.value,
        },
        "page": page,
        "per_page": per_page,
        "total": total,
        "outlets": [
            {
                "id": o.id,
                "name": o.name,
                "code": o.code,
                "owner_name": o.owner_name,
                "mobile": o.mobile,
                "address": o.address,
                "channel": o.channel,
                "gps_lat": o.gps_lat,
                "gps_lng": o.gps_lng,
            }
            for o in outlets
        ],
    }


@router.get("/outlets")
async def outlet_list(
    beat_id: Optional[int] = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    """Paginated approved outlets, optionally filtered by beat."""
    query = scope_outlet_query(
        db.query(Outlet), current_user, db
    ).filter(Outlet.status == OutletStatus.active)
    if beat_id:
        require_beat_access(db, current_user, beat_id, active_only=True)
        query = query.filter(Outlet.beat_id == beat_id)
    query = query.order_by(Outlet.name)
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "items": [
            {
                "id": o.id,
                "name": o.name,
                "code": o.code,
                "beat_id": o.beat_id,
                "territory_id": o.territory_id,
                "owner_name": o.owner_name,
                "mobile": o.mobile,
                "address": o.address,
                "channel": o.channel,
                "gps_lat": o.gps_lat,
                "gps_lng": o.gps_lng,
            }
            for o in items
        ],
    }


@router.get("/products")
async def product_list(
    warehouse_id: Optional[int] = None,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=100, ge=1, le=200),
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    """All active products for mobile offline cache."""
    query = db.query(Product).filter(Product.is_active == True)
    if current_user.company_profile_id:
        query = query.filter(Product.company_profile_id == current_user.company_profile_id)
    total = query.count()
    products = query.order_by(Product.name).offset(
        (page - 1) * per_page
    ).limit(per_page).all()
    return {
        "page": page,
        "per_page": per_page,
        "total": total,
        "items": [
            {
                "id": p.id,
                "name": p.name,
                "erp_id": p.erp_id,
                "sku": p.sku,
                "division": p.division,
                "primary_category": p.primary_category,
                "secondary_category": p.secondary_category,
                "mrp": float(p.mrp) if p.mrp else None,
                "gst_rate": float(p.gst_rate) if p.gst_rate else 0,
                "must_sell": p.must_sell,
                "is_stockable_item": bool(p.is_stockable),
                "category_scope": p.category_type.value if p.category_type else "Sales",
                "warehouse_id": warehouse_id,
                "warehouse_stock_qty": next(
                    (
                        int(stock.stock_qty)
                        for stock in p.warehouse_stocks
                        if warehouse_id and stock.warehouse_id == warehouse_id and stock.is_active
                    ),
                    int(p.stock_qty or 0) if warehouse_id and p.warehouse_id == warehouse_id else 0,
                ),
            }
            for p in products
        ]
    }


@router.get("/config")
async def system_config(
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    """SystemConfiguration for mobile (payment mode, GPS threshold, sync interval)."""
    config = db.query(SystemConfiguration).filter(SystemConfiguration.id == 1).first()
    if not config:
        return {
            "payment_mode": "cash_and_online",
            "denomination_mandatory": False,
            "gps_threshold_metres": 100,
            "sync_interval_seconds": 300,
        }
    pm = config.payment_mode.value if (config and config.payment_mode) else "cash_and_online"
    return {
        "payment_mode": pm,
        "denomination_mandatory": bool(config.denomination_mandatory),
        "gps_threshold_metres": config.gps_threshold_metres or 100,
        "sync_interval_seconds": config.sync_interval_seconds or 300,
    }


# ── Beats & Outlets Management ────────────────────────────────────────────────

class BeatCreateSchema(BaseModel):
    name: str
    code: str
    beat_type: str
    beat_grade: Optional[str] = None
    territory_id: Optional[int] = None
    erp_id: Optional[str] = None


def _format_beat_item(b: Beat):
    pos_names = []
    user_names = []
    for pos in getattr(b, "positions", []):
        if getattr(pos, "is_active", True):
            p_name = f"{pos.name} ({pos.code})" if getattr(pos, "code", None) else pos.name
            if p_name not in pos_names:
                pos_names.append(p_name)
            for u in getattr(pos, "users", []):
                if getattr(u, "is_active", True) and u.full_name not in user_names:
                    user_names.append(u.full_name)

    return {
        "id": b.id,
        "name": b.name,
        "code": b.code,
        "beat_type": b.beat_type.value if hasattr(b.beat_type, "value") else str(b.beat_type or "GT"),
        "beat_grade": b.beat_grade.value if b.beat_grade and hasattr(b.beat_grade, "value") else (str(b.beat_grade) if b.beat_grade else None),
        "territory_id": b.territory_id,
        "l1_position_name": ", ".join(pos_names) if pos_names else "L1 Territory Field Position",
        "assigned_user_name": ", ".join(user_names) if user_names else "Unassigned Rep",
        "active_outlet_count": b.active_outlet_count,
    }


def resolve_user_hierarchy_beats(
    user: User, db: Session, page: int, per_page: int
) -> tuple[List[Beat], int]:
    """
    Collects beats assigned to:
    1. Direct positions assigned to the user.
    2. Any child/subordinate positions under the user's position hierarchy.
    3. Direct beats assigned to subordinate users in the user's hierarchy.
    Returns ONLY beats matching the user's position/hierarchy tree.
    """
    target_beat_ids = set()

    pos_queue = list(getattr(user, "positions", []))
    visited_pos = set()

    while pos_queue:
        pos = pos_queue.pop(0)
        if not pos or pos.id in visited_pos or not getattr(pos, "is_active", True):
            continue
        visited_pos.add(pos.id)

        for b in getattr(pos, "beats", []):
            if getattr(b, "is_active", True):
                target_beat_ids.add(b.id)

        for child in getattr(pos, "direct_reports", []):
            if child and child.id not in visited_pos:
                pos_queue.append(child)

    if target_beat_ids:
        query = db.query(Beat).filter(
            Beat.id.in_(target_beat_ids), Beat.is_active == True
        ).options(
            selectinload(Beat.positions).selectinload(Position.users),
            selectinload(Beat.outlets),
        )
        total = query.count()
        return (
            query.order_by(Beat.name).offset(
                (page - 1) * per_page
            ).limit(per_page).all(),
            total,
        )

    role_val = getattr(user.role, "value", str(user.role or ""))
    if role_val == "admin":
        query = db.query(Beat).filter(Beat.is_active == True).options(
            selectinload(Beat.positions).selectinload(Position.users),
            selectinload(Beat.outlets),
        )
        total = query.count()
        return (
            query.order_by(Beat.name).offset(
                (page - 1) * per_page
            ).limit(per_page).all(),
            total,
        )

    return [], 0


@router.get("/beats")
async def get_beats(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=100, ge=1, le=200),
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    """List active beats filtered strictly by user position hierarchy."""
    beats, total = resolve_user_hierarchy_beats(current_user, db, page, per_page)
    return {
        "page": page, "per_page": per_page, "total": total,
        "items": [_format_beat_item(b) for b in beats]
    }


@router.post("/beats")
async def create_beat(
    payload: BeatCreateSchema,
    current_user: User = Depends(require_restricted_module_api_access),
    db: Session = Depends(get_db),
):
    """Create a new beat."""
    existing = db.query(Beat).filter(Beat.code == payload.code.upper()).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Beat code '{payload.code.upper()}' already exists.")
    
    try:
        bt = BeatType(payload.beat_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid beat type '{payload.beat_type}'.")
    
    bg = None
    if payload.beat_grade:
        try:
            bg = BeatGrade(payload.beat_grade)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid beat grade '{payload.beat_grade}'.")
            
    beat = Beat(
        name=payload.name,
        code=payload.code.upper(),
        beat_type=bt,
        beat_grade=bg,
        territory_id=payload.territory_id,
        erp_id=payload.erp_id,
        is_active=True
    )
    db.add(beat)
    db.commit()
    db.refresh(beat)
    return {
        "id": beat.id,
        "name": beat.name,
        "code": beat.code,
        "beat_type": beat.beat_type.value,
        "beat_grade": beat.beat_grade.value if beat.beat_grade else None,
        "territory_id": beat.territory_id,
    }


class OutletCreateSchema(BaseModel):
    name: str
    code: Optional[str] = None
    owner_name: Optional[str] = None
    mobile: Optional[str] = None
    address: Optional[str] = None
    pincode: Optional[str] = None
    gstin: Optional[str] = None
    channel: Optional[str] = None
    shop_type: Optional[str] = None
    beat_id: int
    territory_id: Optional[int] = None
    gps_lat: Optional[float] = None
    gps_lng: Optional[float] = None
    photo_url: Optional[str] = None


@router.post("/outlets")
async def create_outlet(
    payload: OutletCreateSchema,
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    """Create a new outlet."""
    code = payload.code
    if not code or not code.strip():
        last_outlet = db.query(Outlet).order_by(Outlet.id.desc()).first()
        next_id = (last_outlet.id + 1) if last_outlet else 1
        code = f"OUT{next_id:04d}"
        while db.query(Outlet).filter(Outlet.code == code).first():
            next_id += 1
            code = f"OUT{next_id:04d}"
    else:
        code = code.strip().upper()
        if db.query(Outlet).filter(Outlet.code == code).first():
            raise HTTPException(status_code=400, detail=f"Outlet code '{code}' already exists.")

    if payload.mobile and payload.mobile.strip():
        existing_mobile = db.query(Outlet).filter(Outlet.mobile == payload.mobile.strip()).first()
        if existing_mobile:
            raise HTTPException(status_code=400, detail=f"Mobile number '{payload.mobile.strip()}' is already in use by another outlet.")

    channel_type = None
    if payload.channel:
        try:
            channel_type = ChannelType(payload.channel)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid channel '{payload.channel}'.")

    st = None
    if payload.shop_type:
        try:
            st = ShopType(payload.shop_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid shop_type '{payload.shop_type}'.")

    beat = require_beat_access(
        db, current_user, payload.beat_id, active_only=True
    )

    outlet = Outlet(
        name=payload.name,
        code=code,
        owner_name=payload.owner_name,
        mobile=payload.mobile.strip() if payload.mobile else None,
        address=payload.address,
        pincode=payload.pincode,
        gstin=payload.gstin,
        channel=channel_type,
        shop_type=st,
        beat_id=payload.beat_id,
        territory_id=beat.territory_id,
        gps_lat=payload.gps_lat,
        gps_lng=payload.gps_lng,
        photo_url=payload.photo_url,
        status=OutletStatus.active,
    )
    db.add(outlet)
    db.commit()
    db.refresh(outlet)
    return {
        "id": outlet.id,
        "name": outlet.name,
        "code": outlet.code,
        "owner_name": outlet.owner_name,
        "mobile": outlet.mobile,
        "address": outlet.address,
        "channel": outlet.channel.value if outlet.channel else None,
        "shop_type": outlet.shop_type.value if outlet.shop_type else None,
        "beat_id": outlet.beat_id,
        "photo_url": outlet.photo_url,
        "territory_id": outlet.territory_id,
        "gps_lat": outlet.gps_lat,
        "gps_lng": outlet.gps_lng,
    }


@router.post("/outlets/upload-photo")
async def upload_outlet_photo_api(
    file: UploadFile = File(...),
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    """Mobile API: upload an outlet photo to configured S3/MinIO bucket and return S3 URL."""
    allowed = {"image/jpeg", "image/png", "image/webp", "image/heic"}
    if file.content_type and file.content_type.lower() not in allowed:
        raise HTTPException(status_code=400, detail="Photo must be JPG, PNG, or WEBP format.")
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded photo is empty.")
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Photo exceeds 10 MB limit.")

    from app.utils.s3_service import upload_image_file
    url = upload_image_file(
        db=db,
        file_bytes=contents,
        original_filename=file.filename or "outlet_photo.jpg",
        folder_prefix="outlets",
        content_type=file.content_type or "image/jpeg",
        bucket_type="images",
    )
    return {"url": url}


@router.get("/beats/my")
async def get_my_beats(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=100, ge=1, le=200),
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    """List beats assigned to the authenticated user via their positions."""
    beats, total = resolve_user_hierarchy_beats(current_user, db, page, per_page)
    return {
        "page": page, "per_page": per_page, "total": total,
        "items": [_format_beat_item(b) for b in beats]
    }


@router.get("/beats/l1-positions")
async def get_l1_position_beats(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=100, ge=1, le=200),
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    """
    List beats assigned to positions under the user's position hierarchy.
    """
    beats, total = resolve_user_hierarchy_beats(current_user, db, page, per_page)
    return {
        "page": page, "per_page": per_page, "total": total,
        "items": [_format_beat_item(b) for b in beats]
    }


class OutletLocationUpdateSchema(BaseModel):
    gps_lat: float
    gps_lng: float


class OutletEditSchema(BaseModel):
    name: Optional[str] = None
    owner_name: Optional[str] = None
    mobile: Optional[str] = None
    address: Optional[str] = None
    photo_url: Optional[str] = None
    gps_lat: Optional[float] = None
    gps_lng: Optional[float] = None


@router.get("/outlets/{outlet_id}")
async def get_outlet_detail(
    outlet_id: int,
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    """Detailed view of a single outlet with Mandatory Field Check."""
    o = require_outlet_access(db, current_user, outlet_id)

    missing_fields = []
    if not o.photo_url or not str(o.photo_url).strip():
        missing_fields.append("photo_url")
    if not o.mobile or not str(o.mobile).strip():
        missing_fields.append("mobile")
    if not o.name or not str(o.name).strip():
        missing_fields.append("name")
    if not o.address or not str(o.address).strip():
        missing_fields.append("address")
    if o.gps_lat is None or o.gps_lng is None:
        missing_fields.append("gps")

    is_incomplete = len(missing_fields) > 0

    return {
        "id": o.id,
        "name": o.name,
        "code": o.code,
        "owner_name": o.owner_name,
        "mobile": o.mobile,
        "address": o.address,
        "pincode": o.pincode,
        "gstin": o.gstin,
        "channel": o.channel.value if o.channel else None,
        "shop_type": o.shop_type.value if o.shop_type else None,
        "beat_id": o.beat_id,
        "beat_name": o.beat.name if o.beat else None,
        "territory_id": o.territory_id,
        "gps_lat": o.gps_lat,
        "gps_lng": o.gps_lng,
        "photo_url": o.photo_url,
        "status": o.status.value,
        "is_incomplete": is_incomplete,
        "missing_fields": missing_fields,
    }


@router.post("/outlets/{outlet_id}/edit-request")
async def request_outlet_edit(
    outlet_id: int,
    payload: OutletEditSchema,
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    """Submit outlet edit changes for Approval Flow."""
    o = require_outlet_access(db, current_user, outlet_id)

    # Create AutoFlag / Edit Approval Request
    from app.models.auto_flag import AutoFlag, RiskSeverity, FlagStatus
    flag = AutoFlag(
        entity_type="outlet_edit_approval",
        entity_id=o.id,
        user_id=current_user.id,
        flag_reason=f"Outlet Edit Request submitted by {current_user.full_name}",
        risk_severity=RiskSeverity.low,
        status=FlagStatus.open,
    )
    db.add(flag)

    # Optionally update non-critical pending fields
    if payload.photo_url:
        o.photo_url = payload.photo_url
    if payload.mobile:
        o.mobile = payload.mobile
    if payload.address:
        o.address = payload.address
    if payload.gps_lat is not None and payload.gps_lng is not None:
        o.gps_lat = payload.gps_lat
        o.gps_lng = payload.gps_lng

    db.commit()
    return {"message": "Outlet edit submitted successfully for approval.", "outlet_id": o.id}


@router.patch("/outlets/{outlet_id}/location")
async def update_outlet_location(
    outlet_id: int,
    payload: OutletLocationUpdateSchema,
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    """Update outlet GPS coordinates captured by Field Rep on mobile."""
    o = require_outlet_access(db, current_user, outlet_id)
    o.gps_lat = payload.gps_lat
    o.gps_lng = payload.gps_lng
    db.commit()
    return {"id": o.id, "gps_lat": o.gps_lat, "gps_lng": o.gps_lng, "message": "Outlet location updated successfully."}
