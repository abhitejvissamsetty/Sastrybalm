"""Centralized object-level authorization for geography-scoped Safar records."""

from dataclasses import dataclass, field
from typing import Iterable, Optional

from fastapi import HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models.beat import Beat
from app.models.geography import Geography
from app.models.material_request import MaterialRequest
from app.models.local_distribution import LocalChannelPartner
from app.models.leave import Leave
from app.models.auto_flag import AutoFlag
from app.models.order import Order
from app.models.outlet import Outlet
from app.models.position import Position, position_beats
from app.models.procurement import ProcurementItem, VendorQuotation, WorkOrder
from app.models.recce import RecceInformation
from app.models.asset_capitalization import AssetCapitalization, AssetMaintenanceLog
from app.models.attendance import Attendance
from app.models.expense import Expense
from app.models.payment import Payment
from app.models.timesheet import Timesheet, VisitRecord
from app.models.user import User, UserRole, user_positions
from app.models.vendor import Vendor
from app.models.warehouse import Warehouse


def _role_value(user: User) -> str:
    return getattr(user.role, "value", str(user.role or ""))


def _descendant_ids(db: Session, model, root_ids: Iterable[int], parent_column) -> set[int]:
    resolved = {int(item) for item in root_ids if item}
    frontier = set(resolved)
    while frontier:
        children = {
            row[0]
            for row in db.execute(
                select(model.id).where(parent_column.in_(frontier))
            ).all()
        }
        children -= resolved
        if not children:
            break
        resolved.update(children)
        frontier = children
    return resolved


@dataclass(frozen=True)
class AccessScope:
    user_id: int
    role: str
    unrestricted: bool = False
    position_ids: frozenset[int] = field(default_factory=frozenset)
    user_ids: frozenset[int] = field(default_factory=frozenset)
    geography_ids: frozenset[int] = field(default_factory=frozenset)
    beat_ids: frozenset[int] = field(default_factory=frozenset)
    warehouse_ids: frozenset[int] = field(default_factory=frozenset)
    vendor_ids: frozenset[int] = field(default_factory=frozenset)

    def allows_outlet(self, outlet: Outlet) -> bool:
        if self.unrestricted:
            return True
        if self.role in {
            UserRole.vendor_admin.value,
            UserRole.vendor_technician.value,
            UserRole.qc_manager.value,
        }:
            return False
        if self.role == UserRole.field_rep.value and self.beat_ids:
            return bool(outlet.beat_id and outlet.beat_id in self.beat_ids)
        return bool(
            (outlet.beat_id and outlet.beat_id in self.beat_ids)
            or (outlet.territory_id and outlet.territory_id in self.geography_ids)
        )

    def allows_user(self, target_user_id: Optional[int]) -> bool:
        return bool(
            target_user_id
            and (
                self.unrestricted
                or target_user_id == self.user_id
                or target_user_id in self.user_ids
            )
        )

    def allows_warehouse(self, warehouse_id: Optional[int]) -> bool:
        return bool(warehouse_id and (self.unrestricted or warehouse_id in self.warehouse_ids))

    def allows_geography(self, geography_id: Optional[int]) -> bool:
        return bool(
            geography_id
            and (self.unrestricted or geography_id in self.geography_ids)
        )

    def allows_beat(self, beat_id: Optional[int]) -> bool:
        return bool(beat_id and (self.unrestricted or beat_id in self.beat_ids))

    def allows_position(self, position_id: Optional[int]) -> bool:
        return bool(
            position_id
            and (self.unrestricted or position_id in self.position_ids)
        )

    def allows_vendor(self, vendor_id: Optional[int]) -> bool:
        return bool(vendor_id and (self.unrestricted or vendor_id in self.vendor_ids))

    def allows_material_request(self, item: MaterialRequest) -> bool:
        if self.unrestricted:
            return True
        if self.role in {
            UserRole.vendor_admin.value,
            UserRole.vendor_technician.value,
            UserRole.qc_manager.value,
        }:
            return bool(item.vendor_id and item.vendor_id in self.vendor_ids)
        if self.role == UserRole.field_rep.value:
            return item.user_id == self.user_id
        return bool(
            self.allows_user(item.user_id)
            or (item.outlet is not None and self.allows_outlet(item.outlet))
        )

    def allows_order(self, item: Order) -> bool:
        if self.unrestricted:
            return True
        if self.role in {
            UserRole.vendor_admin.value,
            UserRole.vendor_technician.value,
            UserRole.qc_manager.value,
        }:
            return False
        if self.role == UserRole.field_rep.value:
            return item.user_id == self.user_id
        return bool(
            self.allows_user(item.user_id)
            and (
                (item.outlet is not None and self.allows_outlet(item.outlet))
                or (item.outlet is None and self.allows_warehouse(item.warehouse_id))
            )
        )

    def allows_work_order(self, item: WorkOrder) -> bool:
        if self.unrestricted:
            return True
        if self.role in {
            UserRole.vendor_admin.value,
            UserRole.vendor_technician.value,
            UserRole.qc_manager.value,
        }:
            return bool(item.vendor_id and item.vendor_id in self.vendor_ids)
        return bool(
            (item.material_request is not None and self.allows_material_request(item.material_request))
            or (item.outlet is not None and self.allows_outlet(item.outlet))
        )

    def allows_procurement_item(self, item: ProcurementItem) -> bool:
        if self.unrestricted:
            return True
        if self.role in {
            UserRole.vendor_admin.value,
            UserRole.vendor_technician.value,
            UserRole.qc_manager.value,
        }:
            return bool(item.vendor_id and item.vendor_id in self.vendor_ids)
        return bool(item.outlet is not None and self.allows_outlet(item.outlet))

    def allows_asset(self, item: AssetCapitalization) -> bool:
        if self.unrestricted:
            return True
        if self.role in {
            UserRole.vendor_admin.value,
            UserRole.vendor_technician.value,
            UserRole.qc_manager.value,
        }:
            return bool(item.vendor_id and item.vendor_id in self.vendor_ids)
        if self.role == UserRole.field_rep.value and item.user_id != self.user_id:
            return False
        return bool(item.outlet is not None and self.allows_outlet(item.outlet))

    def allows_channel_partner(self, item: LocalChannelPartner) -> bool:
        return self.allows_geography(item.geography_id)

    def allows_recce(self, item: RecceInformation) -> bool:
        return bool(
            item.material_request is not None
            and self.allows_material_request(item.material_request)
        )

    def allows_quotation(self, item: VendorQuotation) -> bool:
        if self.unrestricted:
            return True
        if self.role in {
            UserRole.vendor_admin.value,
            UserRole.vendor_technician.value,
            UserRole.qc_manager.value,
        }:
            return bool(item.vendor_id and item.vendor_id in self.vendor_ids)
        return bool(
            item.material_request is not None
            and self.allows_material_request(item.material_request)
        )

    def allows_employee_record(self, item) -> bool:
        if self.unrestricted:
            return True
        if self.role in {
            UserRole.vendor_admin.value,
            UserRole.vendor_technician.value,
            UserRole.qc_manager.value,
        }:
            return item.user_id == self.user_id
        return self.allows_user(item.user_id)

    def allows_payment(self, item: Payment) -> bool:
        if not self.allows_employee_record(item):
            return False
        if self.unrestricted or self.role == UserRole.field_rep.value:
            return True
        return bool(item.outlet is not None and self.allows_outlet(item.outlet))

    def allows_visit(self, item: VisitRecord) -> bool:
        if not self.allows_employee_record(item):
            return False
        return bool(
            self.unrestricted
            or (item.outlet is not None and self.allows_outlet(item.outlet))
        )


def build_access_scope(user: User, db: Session) -> AccessScope:
    role = _role_value(user)
    if role == UserRole.admin.value:
        return AccessScope(user_id=user.id, role=role, unrestricted=True)

    root_position_ids = {
        row[0]
        for row in db.execute(
            select(user_positions.c.position_id).where(user_positions.c.user_id == user.id)
        ).all()
    }
    position_ids = _descendant_ids(
        db, Position, root_position_ids, Position.reporting_to_id
    )

    subordinate_user_ids = {
        row[0]
        for row in db.execute(
            select(user_positions.c.user_id).where(
                user_positions.c.position_id.in_(position_ids or {-1})
            )
        ).all()
    }
    subordinate_user_ids.discard(user.id)

    beat_ids = {
        row[0]
        for row in db.execute(
            select(position_beats.c.beat_id).where(
                position_beats.c.position_id.in_(position_ids or {-1})
            )
        ).all()
    }

    root_geo_ids = {
        row[0]
        for row in db.execute(
            select(Beat.territory_id).where(
                Beat.id.in_(beat_ids or {-1}),
                Beat.territory_id.isnot(None),
            )
        ).all()
    }
    if user.geography_id:
        root_geo_ids.add(user.geography_id)
    geography_ids = _descendant_ids(
        db, Geography, root_geo_ids, Geography.parent_id
    )

    # A direct geography assignment grants management coverage for its Beats.
    # Geography inferred only from assigned Beats must not expand horizontally
    # to unrelated Beats in the same territory.
    if user.geography_id and role != UserRole.field_rep.value:
        beat_ids.update(
            row[0]
            for row in db.execute(
                select(Beat.id).where(Beat.territory_id.in_(geography_ids or {-1}))
            ).all()
        )

    warehouse_ids = {
        row[0]
        for row in db.execute(
            select(Warehouse.id).where(
                Warehouse.geography_id.in_(geography_ids or {-1}),
                Warehouse.is_active.is_(True),
            )
        ).all()
    }
    warehouse_ids.update(
        row[0]
        for row in db.execute(
            select(Position.warehouse_id).where(
                Position.id.in_(position_ids or {-1}),
                Position.warehouse_id.isnot(None),
            )
        ).all()
    )
    warehouse_ids.update(
        warehouse.id for warehouse in getattr(user, "scoped_warehouses", []) if warehouse.is_active
    )

    vendor_ids: set[int] = set()
    if role in {UserRole.vendor_admin.value, UserRole.vendor_technician.value}:
        if user.vendor_id:
            vendor_ids.add(user.vendor_id)
    elif role == UserRole.qc_manager.value:
        vendor_ids.update(vendor.id for vendor in getattr(user, "qc_vendors", []))
    else:
        vendor_ids.update(
            row[0]
            for row in db.execute(
                select(Vendor.id).where(Vendor.geography_id.in_(geography_ids or {-1}))
            ).all()
        )

    return AccessScope(
        user_id=user.id,
        role=role,
        position_ids=frozenset(position_ids),
        user_ids=frozenset(subordinate_user_ids),
        geography_ids=frozenset(geography_ids),
        beat_ids=frozenset(beat_ids),
        warehouse_ids=frozenset(warehouse_ids),
        vendor_ids=frozenset(vendor_ids),
    )


def require_outlet_access(
    db: Session,
    user: User,
    outlet_id: int,
    *,
    active_only: bool = False,
) -> Outlet:
    query = db.query(Outlet).filter(Outlet.id == outlet_id)
    if active_only:
        query = query.filter(Outlet.is_active.is_(True))
    outlet = query.first()
    if not outlet:
        raise HTTPException(status_code=404, detail="Outlet not found.")
    if not build_access_scope(user, db).allows_outlet(outlet):
        # Do not disclose whether an out-of-scope record exists.
        raise HTTPException(status_code=404, detail="Outlet not found.")
    return outlet


def require_user_access(db: Session, user: User, target_user_id: int) -> User:
    target = db.query(User).filter(User.id == target_user_id, User.is_active.is_(True)).first()
    if not target or not build_access_scope(user, db).allows_user(target.id):
        raise HTTPException(status_code=404, detail="User not found.")
    return target


def require_warehouse_access(db: Session, user: User, warehouse_id: int) -> Warehouse:
    warehouse = db.query(Warehouse).filter(
        Warehouse.id == warehouse_id, Warehouse.is_active.is_(True)
    ).first()
    if not warehouse or not build_access_scope(user, db).allows_warehouse(warehouse.id):
        raise HTTPException(status_code=404, detail="Warehouse not found.")
    return warehouse


def require_beat_access(
    db: Session, user: User, beat_id: int, *, active_only: bool = False
) -> Beat:
    query = db.query(Beat).filter(Beat.id == beat_id)
    if active_only:
        query = query.filter(Beat.is_active.is_(True))
    beat = query.first()
    if not beat or not build_access_scope(user, db).allows_beat(beat.id):
        raise HTTPException(status_code=404, detail="Beat not found.")
    return beat


def require_position_access(
    db: Session, user: User, position_id: int, *, active_only: bool = False
) -> Position:
    query = db.query(Position).filter(Position.id == position_id)
    if active_only:
        query = query.filter(Position.is_active.is_(True))
    position = query.first()
    if not position or not build_access_scope(user, db).allows_position(position.id):
        raise HTTPException(status_code=404, detail="Position not found.")
    return position


def require_vendor_access(db: Session, user: User, vendor_id: int) -> Vendor:
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor or not build_access_scope(user, db).allows_vendor(vendor.id):
        raise HTTPException(status_code=404, detail="Vendor not found.")
    return vendor


def require_material_request_access(
    db: Session, user: User, material_request_id: int
) -> MaterialRequest:
    item = db.query(MaterialRequest).filter(MaterialRequest.id == material_request_id).first()
    if not item or not build_access_scope(user, db).allows_material_request(item):
        raise HTTPException(status_code=404, detail="Material request not found.")
    return item


def require_order_access(db: Session, user: User, order_id: int) -> Order:
    item = db.query(Order).filter(Order.id == order_id).first()
    if not item or not build_access_scope(user, db).allows_order(item):
        raise HTTPException(status_code=404, detail="Order not found.")
    return item


def require_work_order_access(
    db: Session, user: User, work_order_id: int, *, for_update: bool = False
) -> WorkOrder:
    query = db.query(WorkOrder).filter(WorkOrder.id == work_order_id)
    if for_update:
        query = query.with_for_update()
    item = query.first()
    if not item or not build_access_scope(user, db).allows_work_order(item):
        raise HTTPException(status_code=404, detail="Work order not found.")
    return item


def require_procurement_item_access(
    db: Session, user: User, procurement_item_id: int, *, for_update: bool = False
) -> ProcurementItem:
    query = db.query(ProcurementItem).filter(ProcurementItem.id == procurement_item_id)
    if for_update:
        query = query.with_for_update()
    item = query.first()
    if not item or not build_access_scope(user, db).allows_procurement_item(item):
        raise HTTPException(status_code=404, detail="Procurement item not found.")
    return item


def require_asset_access(
    db: Session, user: User, asset_id: int, *, for_update: bool = False
) -> AssetCapitalization:
    query = db.query(AssetCapitalization).filter(AssetCapitalization.id == asset_id)
    if for_update:
        query = query.with_for_update()
    item = query.first()
    if not item or not build_access_scope(user, db).allows_asset(item):
        raise HTTPException(status_code=404, detail="Asset not found.")
    return item


def require_channel_partner_access(
    db: Session, user: User, channel_partner_id: int
) -> LocalChannelPartner:
    item = db.query(LocalChannelPartner).filter(
        LocalChannelPartner.id == channel_partner_id
    ).first()
    if not item or not build_access_scope(user, db).allows_channel_partner(item):
        raise HTTPException(status_code=404, detail="Channel partner not found.")
    return item


def require_maintenance_access(
    db: Session, user: User, maintenance_log_id: int, *, for_update: bool = False
) -> AssetMaintenanceLog:
    query = db.query(AssetMaintenanceLog).filter(
        AssetMaintenanceLog.id == maintenance_log_id
    )
    if for_update:
        query = query.with_for_update()
    item = query.first()
    if not item or not build_access_scope(user, db).allows_asset(item.asset):
        raise HTTPException(status_code=404, detail="Maintenance log not found.")
    return item


def require_recce_access(
    db: Session, user: User, recce_id: int, *, for_update: bool = False
) -> RecceInformation:
    query = db.query(RecceInformation).filter(RecceInformation.id == recce_id)
    if for_update:
        query = query.with_for_update()
    item = query.first()
    if not item or not build_access_scope(user, db).allows_recce(item):
        raise HTTPException(status_code=404, detail="Recce not found.")
    return item


def require_quotation_access(
    db: Session, user: User, quotation_id: int, *, for_update: bool = False
) -> VendorQuotation:
    query = db.query(VendorQuotation).filter(VendorQuotation.id == quotation_id)
    if for_update:
        query = query.with_for_update()
    item = query.first()
    if not item or not build_access_scope(user, db).allows_quotation(item):
        raise HTTPException(status_code=404, detail="Quotation not found.")
    return item


def scope_outlet_query(query, user: User, db: Session):
    scope = build_access_scope(user, db)
    if scope.unrestricted:
        return query
    if scope.role in {
        UserRole.vendor_admin.value,
        UserRole.vendor_technician.value,
        UserRole.qc_manager.value,
    }:
        return query.filter(Outlet.id == -1)
    if scope.role == UserRole.field_rep.value and scope.beat_ids:
        return query.filter(Outlet.beat_id.in_(scope.beat_ids))
    return query.filter(or_(
        Outlet.beat_id.in_(scope.beat_ids or {-1}),
        Outlet.territory_id.in_(scope.geography_ids or {-1}),
    ))


def scope_asset_query(query, user: User, db: Session):
    scope = build_access_scope(user, db)
    if scope.unrestricted:
        return query
    if scope.role in {
        UserRole.vendor_admin.value,
        UserRole.vendor_technician.value,
        UserRole.qc_manager.value,
    }:
        return query.filter(
            AssetCapitalization.vendor_id.in_(scope.vendor_ids or {-1})
        )
    if scope.role == UserRole.field_rep.value:
        return query.filter(AssetCapitalization.user_id == scope.user_id)
    return query.join(
        Outlet, AssetCapitalization.outlet_id == Outlet.id
    ).filter(or_(
        Outlet.beat_id.in_(scope.beat_ids or {-1}),
        Outlet.territory_id.in_(scope.geography_ids or {-1}),
    ))


def scope_beat_query(query, user: User, db: Session):
    scope = build_access_scope(user, db)
    if scope.unrestricted:
        return query
    return query.filter(Beat.id.in_(scope.beat_ids or {-1}))


def scope_position_query(query, user: User, db: Session):
    scope = build_access_scope(user, db)
    if scope.unrestricted:
        return query
    return query.filter(Position.id.in_(scope.position_ids or {-1}))


def scope_warehouse_query(query, user: User, db: Session):
    scope = build_access_scope(user, db)
    if scope.unrestricted:
        return query
    return query.filter(Warehouse.id.in_(scope.warehouse_ids or {-1}))


def scope_channel_partner_query(query, user: User, db: Session):
    scope = build_access_scope(user, db)
    if scope.unrestricted:
        return query
    return query.filter(
        LocalChannelPartner.geography_id.in_(scope.geography_ids or {-1})
    )


def scope_vendor_query(query, user: User, db: Session):
    scope = build_access_scope(user, db)
    if scope.unrestricted:
        return query
    return query.filter(Vendor.id.in_(scope.vendor_ids or {-1}))


def scope_work_order_query(query, user: User, db: Session):
    scope = build_access_scope(user, db)
    if scope.unrestricted:
        return query
    if scope.role in {
        UserRole.vendor_admin.value,
        UserRole.vendor_technician.value,
        UserRole.qc_manager.value,
    }:
        return query.filter(WorkOrder.vendor_id.in_(scope.vendor_ids or {-1}))
    allowed_users = set(scope.user_ids)
    allowed_users.add(scope.user_id)
    return query.outerjoin(
        MaterialRequest, WorkOrder.material_request_id == MaterialRequest.id
    ).outerjoin(Outlet, WorkOrder.outlet_id == Outlet.id).filter(or_(
        MaterialRequest.user_id.in_(allowed_users),
        Outlet.beat_id.in_(scope.beat_ids or {-1}),
        Outlet.territory_id.in_(scope.geography_ids or {-1}),
    ))


def scope_procurement_item_query(query, user: User, db: Session):
    scope = build_access_scope(user, db)
    if scope.unrestricted:
        return query
    if scope.role in {
        UserRole.vendor_admin.value,
        UserRole.vendor_technician.value,
        UserRole.qc_manager.value,
    }:
        return query.filter(ProcurementItem.vendor_id.in_(scope.vendor_ids or {-1}))
    return query.join(Outlet, ProcurementItem.outlet_id == Outlet.id).filter(or_(
        Outlet.beat_id.in_(scope.beat_ids or {-1}),
        Outlet.territory_id.in_(scope.geography_ids or {-1}),
    ))


def scope_maintenance_query(query, user: User, db: Session):
    scope = build_access_scope(user, db)
    if scope.unrestricted:
        return query
    if scope.role in {
        UserRole.vendor_admin.value,
        UserRole.vendor_technician.value,
        UserRole.qc_manager.value,
    }:
        return query.filter(AssetMaintenanceLog.vendor_id.in_(scope.vendor_ids or {-1}))
    return query.join(
        AssetCapitalization, AssetMaintenanceLog.asset_id == AssetCapitalization.id
    ).join(Outlet, AssetCapitalization.outlet_id == Outlet.id).filter(or_(
        Outlet.beat_id.in_(scope.beat_ids or {-1}),
        Outlet.territory_id.in_(scope.geography_ids or {-1}),
    ))


def scope_order_query(query, user: User, db: Session):
    scope = build_access_scope(user, db)
    if scope.unrestricted:
        return query
    if scope.role in {
        UserRole.vendor_admin.value,
        UserRole.vendor_technician.value,
        UserRole.qc_manager.value,
    }:
        return query.filter(Order.id == -1)
    if scope.role == UserRole.field_rep.value:
        return query.filter(Order.user_id == scope.user_id)
    allowed_users = set(scope.user_ids)
    allowed_users.add(scope.user_id)
    return query.outerjoin(Outlet, Order.outlet_id == Outlet.id).filter(
        Order.user_id.in_(allowed_users),
        or_(
            and_(
                Order.outlet_id.isnot(None),
                or_(
                    Outlet.beat_id.in_(scope.beat_ids or {-1}),
                    Outlet.territory_id.in_(scope.geography_ids or {-1}),
                ),
            ),
            and_(
                Order.outlet_id.is_(None),
                Order.warehouse_id.in_(scope.warehouse_ids or {-1}),
            ),
        ),
    )


def scope_material_request_query(query, user: User, db: Session):
    scope = build_access_scope(user, db)
    if scope.unrestricted:
        return query
    if scope.role in {
        UserRole.vendor_admin.value,
        UserRole.vendor_technician.value,
        UserRole.qc_manager.value,
    }:
        return query.filter(MaterialRequest.vendor_id.in_(scope.vendor_ids or {-1}))
    if scope.role == UserRole.field_rep.value:
        return query.filter(MaterialRequest.user_id == scope.user_id)
    allowed_users = set(scope.user_ids)
    allowed_users.add(scope.user_id)
    return query.outerjoin(Outlet, MaterialRequest.outlet_id == Outlet.id).filter(
        or_(
            MaterialRequest.user_id.in_(allowed_users),
            Outlet.beat_id.in_(scope.beat_ids or {-1}),
            Outlet.territory_id.in_(scope.geography_ids or {-1}),
        )
    )


def scope_recce_query(query, user: User, db: Session):
    allowed_material_requests = scope_material_request_query(
        db.query(MaterialRequest.id), user, db
    ).subquery()
    return query.filter(
        RecceInformation.material_request_id.in_(allowed_material_requests)
    )


def scope_quotation_query(query, user: User, db: Session):
    scope = build_access_scope(user, db)
    if scope.unrestricted:
        return query
    if scope.role in {
        UserRole.vendor_admin.value,
        UserRole.vendor_technician.value,
        UserRole.qc_manager.value,
    }:
        return query.filter(
            VendorQuotation.vendor_id.in_(scope.vendor_ids or {-1})
        )
    allowed_material_requests = scope_material_request_query(
        db.query(MaterialRequest.id), user, db
    ).subquery()
    return query.filter(
        VendorQuotation.material_request_id.in_(allowed_material_requests)
    )


def scope_employee_record_query(query, model, user: User, db: Session):
    scope = build_access_scope(user, db)
    if scope.unrestricted:
        return query
    if scope.role in {
        UserRole.vendor_admin.value,
        UserRole.vendor_technician.value,
        UserRole.qc_manager.value,
        UserRole.field_rep.value,
    }:
        return query.filter(model.user_id == scope.user_id)
    allowed_users = set(scope.user_ids)
    allowed_users.add(scope.user_id)
    return query.filter(model.user_id.in_(allowed_users))


def scope_payment_query(query, user: User, db: Session):
    scope = build_access_scope(user, db)
    query = scope_employee_record_query(query, Payment, user, db)
    if scope.unrestricted or scope.role == UserRole.field_rep.value:
        return query
    return query.join(Outlet, Payment.outlet_id == Outlet.id).filter(or_(
        Outlet.beat_id.in_(scope.beat_ids or {-1}),
        Outlet.territory_id.in_(scope.geography_ids or {-1}),
    ))


def scope_visit_query(query, user: User, db: Session):
    scope = build_access_scope(user, db)
    query = scope_employee_record_query(query, VisitRecord, user, db)
    if scope.unrestricted:
        return query
    return query.join(Outlet, VisitRecord.outlet_id == Outlet.id).filter(or_(
        Outlet.beat_id.in_(scope.beat_ids or {-1}),
        Outlet.territory_id.in_(scope.geography_ids or {-1}),
    ))


def scope_user_query(query, user: User, db: Session, *, include_self: bool = True):
    scope = build_access_scope(user, db)
    if scope.unrestricted:
        return query
    allowed_users = set(scope.user_ids)
    if include_self:
        allowed_users.add(scope.user_id)
    return query.filter(User.id.in_(allowed_users or {-1}))


def _require_employee_record(db, user, model, record_id, detail):
    item = db.query(model).filter(model.id == record_id).first()
    if not item or not build_access_scope(user, db).allows_employee_record(item):
        raise HTTPException(status_code=404, detail=detail)
    return item


def require_expense_access(db: Session, user: User, expense_id: int) -> Expense:
    return _require_employee_record(db, user, Expense, expense_id, "Expense not found.")


def require_leave_access(db: Session, user: User, leave_id: int) -> Leave:
    return _require_employee_record(db, user, Leave, leave_id, "Leave request not found.")


def require_flag_access(db: Session, user: User, flag_id: int) -> AutoFlag:
    return _require_employee_record(db, user, AutoFlag, flag_id, "Flag not found.")


def require_attendance_access(db: Session, user: User, attendance_id: int) -> Attendance:
    return _require_employee_record(
        db, user, Attendance, attendance_id, "Attendance not found."
    )


def require_timesheet_access(db: Session, user: User, timesheet_id: int) -> Timesheet:
    return _require_employee_record(
        db, user, Timesheet, timesheet_id, "Timesheet not found."
    )


def require_payment_access(db: Session, user: User, payment_id: int) -> Payment:
    item = db.query(Payment).filter(Payment.id == payment_id).first()
    if not item or not build_access_scope(user, db).allows_payment(item):
        raise HTTPException(status_code=404, detail="Payment not found.")
    return item


def require_visit_access(db: Session, user: User, visit_id: int) -> VisitRecord:
    item = db.query(VisitRecord).filter(VisitRecord.id == visit_id).first()
    if not item or not build_access_scope(user, db).allows_visit(item):
        raise HTTPException(status_code=404, detail="Visit not found.")
    return item
