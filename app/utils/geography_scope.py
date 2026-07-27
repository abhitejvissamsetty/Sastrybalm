"""
Geography and Warehouse Scoping Utility — Centralized permission scoping for users,
territory managers, vendors, outlets, warehouses, beats, and inventory.
"""
from typing import Optional, List
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.models.geography import Geography, GeoLevel
from app.models.warehouse import Warehouse
from app.models.user_position import UserPosition
from app.models.position import Position


def get_user_allowed_geography_ids(user: Optional[User], db: Session) -> Optional[List[int]]:
    """
    Returns list of allowed Geography IDs for a user.
    If Admin, returns None (indicating unlimited access across all geographies).
    If Territory Manager, resolves assigned Region and all child Territories under it.
    """
    if not user:
        return []
    
    if user.role == UserRole.admin:
        return None  # None indicates no restriction

    region_id = user.geography_id

    # If geography_id not directly set on user, check active UserPosition -> Position -> geography_id
    if not region_id:
        up = db.query(UserPosition).filter(
            UserPosition.user_id == user.id,
            UserPosition.is_active == True
        ).first()
        if up and up.position and up.position.geography_id:
            pos_geo = db.query(Geography).filter(Geography.id == up.position.geography_id).first()
            if pos_geo:
                if pos_geo.level == GeoLevel.region:
                    region_id = pos_geo.id
                elif pos_geo.level == GeoLevel.territory and pos_geo.parent_id:
                    region_id = pos_geo.parent_id

    if not region_id:
        return []

    # Get the region itself and all child territories
    child_ids = [
        g.id for g in db.query(Geography).filter(
            Geography.parent_id == region_id,
            Geography.is_active == True
        ).all()
    ]
    return [region_id] + child_ids


def get_user_allowed_warehouse_ids(user: Optional[User], db: Session) -> Optional[List[int]]:
    """
    Returns list of allowed Warehouse IDs for a user based on their Geography scope.
    If Admin, returns None (unlimited access to all warehouses).
    For Territory Manager, returns IDs of warehouses mapped to allowed geographies.
    """
    if not user:
        return []
        
    allowed_geo_ids = get_user_allowed_geography_ids(user, db)
    if allowed_geo_ids is None:
        return None  # Admin has access to all warehouses

    if not allowed_geo_ids:
        return []

    warehouses = db.query(Warehouse).filter(
        Warehouse.geography_id.in_(allowed_geo_ids),
        Warehouse.is_active == True
    ).all()

    return [w.id for w in warehouses]
