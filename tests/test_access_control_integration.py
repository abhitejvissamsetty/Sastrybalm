import pytest
from fastapi import HTTPException

from app.models.beat import Beat
from app.models.geography import Geography, GeoLevel
from app.models.outlet import Outlet
from app.models.position import Position, PositionLevel
from app.models.user import User, UserRole
from app.models.attendance import Attendance
from app.models.expense import Expense, ExpenseCategory
from app.models.timesheet import Timesheet
from app.models.vendor import Vendor
from app.models.local_distribution import LocalChannelPartner
from datetime import date
from app.services.access_control import (
    build_access_scope,
    require_beat_access,
    require_outlet_access,
    require_user_access,
    require_vendor_access,
    require_channel_partner_access,
    scope_outlet_query,
    scope_employee_record_query,
)


def create_user(db, *, username, role, positions=()):
    user = User(
        email=f"{username}@example.test",
        username=username,
        full_name=username.replace("_", " ").title(),
        role=role,
        is_active=True,
    )
    user.positions.extend(positions)
    db.add(user)
    db.flush()
    return user


def test_cross_territory_outlet_access_is_denied(db_session):
    db = db_session
    region = Geography(name="Test Region", code="TEST-REGION", level=GeoLevel.region)
    territory_a = Geography(
        name="Territory A", code="TEST-A", level=GeoLevel.territory, parent=region
    )
    territory_b = Geography(
        name="Territory B", code="TEST-B", level=GeoLevel.territory, parent=region
    )
    beat_a = Beat(name="Beat A", code="BEAT-A", territory=territory_a)
    beat_b = Beat(name="Beat B", code="BEAT-B", territory=territory_b)
    position_a = Position(name="Rep A", code="POS-A", level=PositionLevel.L1)
    position_b = Position(name="Rep B", code="POS-B", level=PositionLevel.L1)
    position_a.beats.append(beat_a)
    position_b.beats.append(beat_b)
    rep_a = create_user(
        db, username="rep_a", role=UserRole.field_rep, positions=(position_a,)
    )
    rep_b = create_user(
        db, username="rep_b", role=UserRole.field_rep, positions=(position_b,)
    )
    outlet_a = Outlet(name="Outlet A", code="OUT-A", beat=beat_a, territory=territory_a)
    outlet_b = Outlet(name="Outlet B", code="OUT-B", beat=beat_b, territory=territory_b)
    db.add_all([outlet_a, outlet_b])
    db.commit()

    assert require_outlet_access(db, rep_a, outlet_a.id).id == outlet_a.id
    assert require_beat_access(db, rep_a, beat_a.id).id == beat_a.id
    with pytest.raises(HTTPException) as denied:
        require_outlet_access(db, rep_a, outlet_b.id)
    assert denied.value.status_code == 404
    with pytest.raises(HTTPException) as beat_denied:
        require_beat_access(db, rep_a, beat_b.id)
    assert beat_denied.value.status_code == 404

    visible_a = scope_outlet_query(db.query(Outlet), rep_a, db).all()
    visible_b = scope_outlet_query(db.query(Outlet), rep_b, db).all()
    assert [item.id for item in visible_a] == [outlet_a.id]
    assert [item.id for item in visible_b] == [outlet_b.id]


def test_manager_scope_contains_only_reporting_subtree(db_session):
    db = db_session
    territory = Geography(
        name="Manager Territory", code="MGR-TERR", level=GeoLevel.territory
    )
    managed_beat = Beat(name="Managed Beat", code="M-BEAT", territory=territory)
    other_beat = Beat(name="Other Beat", code="O-BEAT", territory=territory)
    manager_position = Position(
        name="Manager", code="MGR-POS", level=PositionLevel.L3
    )
    managed_position = Position(
        name="Managed Rep",
        code="MANAGED-POS",
        level=PositionLevel.L1,
        reporting_to=manager_position,
    )
    other_position = Position(
        name="Other Rep", code="OTHER-POS", level=PositionLevel.L1
    )
    managed_position.beats.append(managed_beat)
    other_position.beats.append(other_beat)
    manager = create_user(
        db,
        username="manager",
        role=UserRole.territory_manager,
        positions=(manager_position,),
    )
    managed_rep = create_user(
        db,
        username="managed_rep",
        role=UserRole.field_rep,
        positions=(managed_position,),
    )
    other_rep = create_user(
        db,
        username="other_rep",
        role=UserRole.field_rep,
        positions=(other_position,),
    )
    db.commit()

    scope = build_access_scope(manager, db)
    assert managed_rep.id in scope.user_ids
    assert other_rep.id not in scope.user_ids
    assert managed_beat.id in scope.beat_ids
    assert other_beat.id not in scope.beat_ids
    assert require_user_access(db, manager, managed_rep.id).id == managed_rep.id
    with pytest.raises(HTTPException) as user_denied:
        require_user_access(db, manager, other_rep.id)
    assert user_denied.value.status_code == 404

    managed_attendance = Attendance(user_id=managed_rep.id, date=date(2026, 7, 29))
    other_attendance = Attendance(user_id=other_rep.id, date=date(2026, 7, 29))
    managed_expense = Expense(
        user_id=managed_rep.id,
        category=ExpenseCategory.travel,
        amount=100,
        expense_date=date(2026, 7, 29),
    )
    other_timesheet = Timesheet(
        user_id=other_rep.id,
        work_date=date(2026, 7, 29),
    )
    db.add_all([
        managed_attendance,
        other_attendance,
        managed_expense,
        other_timesheet,
    ])
    db.commit()

    assert scope_employee_record_query(
        db.query(Attendance), Attendance, manager, db
    ).all() == [managed_attendance]
    assert scope_employee_record_query(
        db.query(Expense), Expense, manager, db
    ).all() == [managed_expense]
    assert scope_employee_record_query(
        db.query(Timesheet), Timesheet, manager, db
    ).all() == []


def test_cross_vendor_and_channel_partner_access_is_denied(db_session):
    db = db_session
    geography_a = Geography(
        name="Vendor Territory A", code="VEND-A", level=GeoLevel.territory
    )
    geography_b = Geography(
        name="Vendor Territory B", code="VEND-B", level=GeoLevel.territory
    )
    vendor_a = Vendor(name="Vendor A", geography=geography_a)
    vendor_b = Vendor(name="Vendor B", geography=geography_b)
    partner_a = LocalChannelPartner(
        name="Partner A", geography=geography_a
    )
    partner_b = LocalChannelPartner(
        name="Partner B", geography=geography_b
    )
    db.add_all([vendor_a, vendor_b, partner_a, partner_b])
    db.flush()
    vendor_user = User(
        email="vendor-a@example.test",
        username="vendor_a_user",
        full_name="Vendor A User",
        role=UserRole.vendor_admin,
        vendor_id=vendor_a.id,
        is_active=True,
    )
    manager = User(
        email="manager-a@example.test",
        username="manager_a",
        full_name="Manager A",
        role=UserRole.territory_manager,
        geography_id=geography_a.id,
        is_active=True,
    )
    db.add_all([vendor_user, manager])
    db.commit()

    assert require_vendor_access(db, vendor_user, vendor_a.id) is vendor_a
    with pytest.raises(HTTPException) as vendor_denied:
        require_vendor_access(db, vendor_user, vendor_b.id)
    assert vendor_denied.value.status_code == 404

    assert require_channel_partner_access(db, manager, partner_a.id) is partner_a
    with pytest.raises(HTTPException) as partner_denied:
        require_channel_partner_access(db, manager, partner_b.id)
    assert partner_denied.value.status_code == 404
