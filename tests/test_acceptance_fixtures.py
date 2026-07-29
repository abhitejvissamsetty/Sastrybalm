from app.models.position import PositionLevel
from app.models.user import UserRole
from app.services.access_control import (
    build_access_scope,
    scope_outlet_query,
    scope_vendor_query,
    scope_warehouse_query,
)
from app.models.outlet import Outlet
from app.models.vendor import Vendor
from app.models.warehouse import Warehouse


def test_acceptance_factory_contains_every_role_and_level(acceptance_data):
    users = acceptance_data["users"]
    assert users["admin"].role == UserRole.admin
    assert users["l4"].positions[0].level == PositionLevel.L4
    assert users["l3"].positions[0].level == PositionLevel.L3
    assert users["l2"].positions[0].level == PositionLevel.L2
    assert users["l1"].positions[0].level == PositionLevel.L1
    assert users["vendor_admin"].role == UserRole.vendor_admin
    assert users["vendor_technician"].role == UserRole.vendor_technician
    assert users["qc_manager"].role == UserRole.qc_manager

    assert users["l1"].positions[0].reporting_to is users["l2"].positions[0]
    assert users["l2"].positions[0].reporting_to is users["l3"].positions[0]
    assert users["l3"].positions[0].reporting_to is users["l4"].positions[0]
    assert users["vendor_admin"].vendor is acceptance_data["vendors"]["a"]
    assert acceptance_data["vendors"]["a"] in users["qc_manager"].qc_vendors


def test_acceptance_factory_has_two_complete_isolated_branches(
    db_session, acceptance_data
):
    assert len(acceptance_data["geographies"]) == 6
    assert set(acceptance_data["warehouses"]) == {"a", "b"}
    assert set(acceptance_data["products"]) == {"sales", "marketing"}
    assert set(acceptance_data["vendors"]) == {"a", "b"}
    assert set(acceptance_data["partners"]) == {"a", "b"}
    assert set(acceptance_data["beats"]) == {"a", "b"}
    assert set(acceptance_data["outlets"]) == {"a", "b"}

    l3 = acceptance_data["users"]["l3"]
    scope = build_access_scope(l3, db_session)
    assert acceptance_data["users"]["l1"].id in scope.user_ids
    assert acceptance_data["users"]["other_l1"].id not in scope.user_ids

    outlets = scope_outlet_query(db_session.query(Outlet), l3, db_session).all()
    warehouses = scope_warehouse_query(
        db_session.query(Warehouse), l3, db_session
    ).all()
    vendors = scope_vendor_query(db_session.query(Vendor), l3, db_session).all()
    assert [item.code for item in outlets] == ["ACC-OA"]
    assert [item.code for item in warehouses] == ["ACC-WHA"]
    assert [item.name for item in vendors] == ["Vendor A"]
