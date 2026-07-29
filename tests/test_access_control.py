from types import SimpleNamespace

from app.models.user import UserRole
from app.services.access_control import AccessScope


def outlet(*, beat_id=None, territory_id=None):
    return SimpleNamespace(beat_id=beat_id, territory_id=territory_id)


def material_request(*, user_id, vendor_id=None, request_outlet=None):
    return SimpleNamespace(user_id=user_id, vendor_id=vendor_id, outlet=request_outlet)


def order(*, user_id, order_outlet=None, warehouse_id=None):
    return SimpleNamespace(
        user_id=user_id, outlet=order_outlet, warehouse_id=warehouse_id
    )


def work_order(*, vendor_id=None, request=None, work_outlet=None):
    return SimpleNamespace(
        vendor_id=vendor_id, material_request=request, outlet=work_outlet
    )


def asset(*, user_id, vendor_id=None, asset_outlet=None):
    return SimpleNamespace(
        user_id=user_id, vendor_id=vendor_id, outlet=asset_outlet
    )


def child_record(*, request=None, vendor_id=None):
    return SimpleNamespace(material_request=request, vendor_id=vendor_id)


def employee_record(*, user_id, record_outlet=None):
    return SimpleNamespace(user_id=user_id, outlet=record_outlet)


def test_admin_scope_is_unrestricted():
    scope = AccessScope(user_id=1, role=UserRole.admin.value, unrestricted=True)

    assert scope.allows_outlet(outlet(beat_id=999, territory_id=999))
    assert scope.allows_user(999)
    assert scope.allows_warehouse(999)
    assert scope.allows_vendor(999)


def test_field_scope_allows_only_assigned_beat_or_geography():
    scope = AccessScope(
        user_id=10,
        role=UserRole.field_rep.value,
        beat_ids=frozenset({20}),
        geography_ids=frozenset({30}),
    )

    assert scope.allows_outlet(outlet(beat_id=20, territory_id=999))
    assert not scope.allows_outlet(outlet(beat_id=999, territory_id=30))
    assert not scope.allows_outlet(outlet(beat_id=21, territory_id=31))
    assert not scope.allows_outlet(outlet())


def test_vendor_roles_cannot_use_general_outlet_access():
    for role in (UserRole.vendor_admin.value, UserRole.vendor_technician.value):
        scope = AccessScope(
            user_id=10,
            role=role,
            beat_ids=frozenset({20}),
            geography_ids=frozenset({30}),
            vendor_ids=frozenset({40}),
        )

        assert not scope.allows_outlet(outlet(beat_id=20, territory_id=30))
        assert scope.allows_vendor(40)
        assert not scope.allows_vendor(41)


def test_qc_manager_is_restricted_to_assigned_vendors():
    scope = AccessScope(
        user_id=10,
        role=UserRole.qc_manager.value,
        vendor_ids=frozenset({40, 41}),
    )

    assert scope.allows_vendor(40)
    assert scope.allows_vendor(41)
    assert not scope.allows_vendor(42)
    assert not scope.allows_outlet(outlet(beat_id=20, territory_id=30))


def test_user_and_warehouse_access_are_membership_scoped():
    scope = AccessScope(
        user_id=10,
        role=UserRole.territory_manager.value,
        user_ids=frozenset({11, 12}),
        warehouse_ids=frozenset({50}),
    )

    assert scope.allows_user(10)
    assert scope.allows_user(11)
    assert not scope.allows_user(13)
    assert scope.allows_warehouse(50)
    assert not scope.allows_warehouse(51)


def test_material_request_access_follows_owner_hierarchy_or_vendor_assignment():
    rep = AccessScope(user_id=10, role=UserRole.field_rep.value)
    manager = AccessScope(
        user_id=20,
        role=UserRole.territory_manager.value,
        user_ids=frozenset({10}),
    )
    vendor = AccessScope(
        user_id=30,
        role=UserRole.vendor_admin.value,
        vendor_ids=frozenset({40}),
    )
    item = material_request(user_id=10, vendor_id=40)

    assert rep.allows_material_request(item)
    assert manager.allows_material_request(item)
    assert vendor.allows_material_request(item)
    assert not AccessScope(
        user_id=11, role=UserRole.field_rep.value
    ).allows_material_request(item)
    assert not AccessScope(
        user_id=31,
        role=UserRole.vendor_admin.value,
        vendor_ids=frozenset({41}),
    ).allows_material_request(item)


def test_order_access_requires_owner_and_object_scope():
    manager = AccessScope(
        user_id=20,
        role=UserRole.territory_manager.value,
        user_ids=frozenset({10}),
        beat_ids=frozenset({30}),
        warehouse_ids=frozenset({40}),
    )

    assert manager.allows_order(order(user_id=10, order_outlet=outlet(beat_id=30)))
    assert manager.allows_order(order(user_id=10, warehouse_id=40))
    assert not manager.allows_order(order(user_id=11, order_outlet=outlet(beat_id=30)))
    assert not manager.allows_order(order(user_id=10, warehouse_id=41))


def test_work_order_and_asset_access_respect_vendor_or_outlet_scope():
    vendor = AccessScope(
        user_id=20,
        role=UserRole.vendor_technician.value,
        vendor_ids=frozenset({50}),
    )
    manager = AccessScope(
        user_id=30,
        role=UserRole.territory_manager.value,
        user_ids=frozenset({10}),
        beat_ids=frozenset({60}),
    )
    scoped_request = material_request(
        user_id=10, request_outlet=outlet(beat_id=60)
    )

    assert vendor.allows_work_order(work_order(vendor_id=50))
    assert not vendor.allows_work_order(work_order(vendor_id=51))
    assert manager.allows_work_order(work_order(request=scoped_request))
    assert vendor.allows_asset(asset(user_id=99, vendor_id=50))
    assert not vendor.allows_asset(asset(user_id=99, vendor_id=51))
    assert manager.allows_asset(
        asset(user_id=10, asset_outlet=outlet(beat_id=60))
    )


def test_recce_and_quotation_inherit_material_request_or_vendor_scope():
    manager = AccessScope(
        user_id=30,
        role=UserRole.territory_manager.value,
        user_ids=frozenset({10}),
    )
    vendor = AccessScope(
        user_id=40,
        role=UserRole.vendor_admin.value,
        vendor_ids=frozenset({50}),
    )
    request = material_request(user_id=10, vendor_id=50)

    assert manager.allows_recce(child_record(request=request))
    assert manager.allows_quotation(child_record(request=request, vendor_id=50))
    assert vendor.allows_recce(child_record(request=request))
    assert vendor.allows_quotation(child_record(request=request, vendor_id=50))
    assert not vendor.allows_quotation(child_record(request=request, vendor_id=51))


def test_employee_financial_and_visit_records_require_hierarchy_and_outlet_scope():
    manager = AccessScope(
        user_id=20,
        role=UserRole.territory_manager.value,
        user_ids=frozenset({10}),
        beat_ids=frozenset({30}),
    )
    rep = AccessScope(user_id=10, role=UserRole.field_rep.value)

    assert manager.allows_employee_record(employee_record(user_id=10))
    assert not manager.allows_employee_record(employee_record(user_id=11))
    assert rep.allows_payment(employee_record(user_id=10))
    assert not rep.allows_payment(employee_record(user_id=11))
    assert manager.allows_payment(
        employee_record(user_id=10, record_outlet=outlet(beat_id=30))
    )
    assert not manager.allows_payment(
        employee_record(user_id=10, record_outlet=outlet(beat_id=31))
    )
    assert manager.allows_visit(
        employee_record(user_id=10, record_outlet=outlet(beat_id=30))
    )
    assert not manager.allows_visit(
        employee_record(user_id=10, record_outlet=outlet(beat_id=31))
    )
