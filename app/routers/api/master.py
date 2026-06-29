from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_api_auth
from app.models.beat import Beat, BeatType, BeatGrade
from app.models.company import SystemConfiguration
from app.models.geography import Geography
from app.models.outlet import Outlet, OutletStatus, ChannelType, ShopType
from app.models.product import Product
from app.models.user import User

router = APIRouter(prefix="/api/v1", tags=["mobile-master"])


@router.get("/geography/tree")
async def geography_tree(
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

    roots = (
        db.query(Geography)
        .filter(Geography.parent_id == None, Geography.is_active == True)
        .order_by(Geography.name)
        .all()
    )
    return {"tree": [_node(g) for g in roots]}


@router.get("/beats/daily-plan")
async def beat_daily_plan(
    beat_id: int = Query(...),
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    """Ordered outlet list for a beat (approved outlets only)."""
    beat = db.query(Beat).filter(Beat.id == beat_id, Beat.is_active == True).first()
    if not beat:
        return {"beat": None, "outlets": []}

    outlets = (
        db.query(Outlet)
        .filter(Outlet.beat_id == beat_id, Outlet.status == OutletStatus.active)
        .order_by(Outlet.name)
        .all()
    )
    return {
        "beat": {
            "id": beat.id,
            "name": beat.name,
            "code": beat.code,
            "beat_type": beat.beat_type.value,
        },
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
    query = db.query(Outlet).filter(Outlet.status == OutletStatus.active)
    if beat_id:
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
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    """All active products for mobile offline cache."""
    query = db.query(Product).filter(Product.is_active == True)
    if current_user.company_profile_id:
        query = query.filter(Product.company_profile_id == current_user.company_profile_id)
    products = query.order_by(Product.name).all()
    return {
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
    return {
        "payment_mode": config.payment_mode.value,
        "denomination_mandatory": config.denomination_mandatory,
        "gps_threshold_metres": config.gps_threshold_metres,
        "sync_interval_seconds": config.sync_interval_seconds,
    }


# ── Beats & Outlets Management ────────────────────────────────────────────────

class BeatCreateSchema(BaseModel):
    name: str
    code: str
    beat_type: str
    beat_grade: Optional[str] = None
    territory_id: Optional[int] = None
    erp_id: Optional[str] = None


@router.get("/beats")
async def get_beats(
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    """List all active beats."""
    beats = db.query(Beat).filter(Beat.is_active == True).order_by(Beat.name).all()
    return {
        "items": [
            {
                "id": b.id,
                "name": b.name,
                "code": b.code,
                "beat_type": b.beat_type.value,
                "beat_grade": b.beat_grade.value if b.beat_grade else None,
                "territory_id": b.territory_id,
            }
            for b in beats
        ]
    }


@router.post("/beats")
async def create_beat(
    payload: BeatCreateSchema,
    current_user: User = Depends(require_api_auth),
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

    beat = db.query(Beat).filter(Beat.id == payload.beat_id, Beat.is_active == True).first()
    if not beat:
        raise HTTPException(status_code=400, detail="Active beat is mandatory and must exist.")

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
        territory_id=payload.territory_id or beat.territory_id,
        gps_lat=payload.gps_lat,
        gps_lng=payload.gps_lng,
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
        "territory_id": outlet.territory_id,
        "gps_lat": outlet.gps_lat,
        "gps_lng": outlet.gps_lng,
    }

