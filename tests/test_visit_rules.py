import asyncio

import pytest
from fastapi import HTTPException

from app.models.order import Order
from app.models.timesheet import VisitRecord
from app.routers.api.operations import (
    checkout_visit,
    create_joint_visit,
    create_order,
    log_visit,
)
from app.utils.timezone import ist_now


def test_visit_rejects_invalid_gps_and_classifies_distance(
    db_session, acceptance_data, monkeypatch
):
    monkeypatch.setattr("app.services.auto_flagging.flag_visit_gps", lambda *_: None)
    rep = acceptance_data["users"]["l1"]
    outlet = acceptance_data["outlets"]["a"]

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            log_visit(
                outlet.id, 91, outlet.gps_lng,
                idempotency_key="visit-invalid-gps",
                current_user=rep, db=db_session,
            )
        )
    assert exc.value.status_code == 400

    result = asyncio.run(
        log_visit(
            outlet.id,
            outlet.gps_lat,
            outlet.gps_lng,
            idempotency_key="visit-in-location",
            current_user=rep,
            db=db_session,
        )
    )
    visit = db_session.query(VisitRecord).filter_by(id=result["id"]).one()
    assert visit.visit_type == "in_location"
    assert visit.distance_from_outlet == pytest.approx(0)

    result = asyncio.run(
        log_visit(
            outlet.id,
            outlet.gps_lat + 1,
            outlet.gps_lng + 1,
            idempotency_key="visit-out-of-range",
            current_user=rep,
            db=db_session,
        )
    )
    visit = db_session.query(VisitRecord).filter_by(id=result["id"]).one()
    assert visit.visit_type == "out_of_range"


def test_checkout_requires_order_or_no_order_reason(
    db_session, acceptance_data, monkeypatch
):
    rep = acceptance_data["users"]["l1"]
    outlet = acceptance_data["outlets"]["a"]
    visit = VisitRecord(
        user=rep,
        outlet=outlet,
        visit_time=ist_now(),
        gps_lat=outlet.gps_lat,
        gps_lng=outlet.gps_lng,
    )
    db_session.add(visit)
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            checkout_visit(visit.id, current_user=rep, db=db_session)
        )
    assert exc.value.status_code == 400
    assert "no-order reason" in exc.value.detail

    monkeypatch.setattr(
        "app.services.timesheet_service.sync_auto_timesheet_line_item",
        lambda *_: None,
    )
    monkeypatch.setattr(
        "app.services.auto_flagging.flag_visit_duration", lambda *_: None
    )
    result = asyncio.run(
        checkout_visit(
            visit.id,
            no_order_reason="Outlet owner unavailable",
            current_user=rep,
            db=db_session,
        )
    )
    assert result["checkout_time"]
    assert visit.no_order_reason == "Outlet owner unavailable"


def test_secondary_order_links_mandatory_visit(
    db_session, acceptance_data
):
    rep = acceptance_data["users"]["l1"]
    outlet = acceptance_data["outlets"]["a"]
    product = acceptance_data["products"]["sales"]
    visit = VisitRecord(
        user=rep,
        outlet=outlet,
        visit_time=ist_now(),
        gps_lat=outlet.gps_lat,
        gps_lng=outlet.gps_lng,
    )
    db_session.add(visit)
    db_session.commit()

    result = asyncio.run(
        create_order(
            items=[{
                "product_id": product.id,
                "quantity": 1,
                "unit_price": 118,
                "gst_rate": 18,
            }],
            outlet_id=outlet.id,
            visit_id=visit.id,
            warehouse_id=acceptance_data["warehouses"]["a"].id,
            idempotency_key="secondary-order-create",
            current_user=rep,
            db=db_session,
        )
    )
    replay = asyncio.run(
        create_order(
            items=[{
                "product_id": product.id,
                "quantity": 1,
                "unit_price": 118,
                "gst_rate": 18,
            }],
            outlet_id=outlet.id,
            visit_id=visit.id,
            warehouse_id=acceptance_data["warehouses"]["a"].id,
            idempotency_key="secondary-order-create",
            current_user=rep,
            db=db_session,
        )
    )
    db_session.refresh(visit)
    order = db_session.query(Order).filter_by(id=result["id"]).one()
    assert replay == result
    assert db_session.query(Order).filter_by(
        order_number=result["order_number"]
    ).count() == 1
    assert order.visit_id == visit.id
    assert visit.order_id == order.id


def test_joint_working_enforces_hierarchy_and_outcome(
    db_session, acceptance_data
):
    manager = acceptance_data["users"]["l3"]
    subordinate = acceptance_data["users"]["l1"]
    outsider = acceptance_data["users"]["other_l1"]
    outlet = acceptance_data["outlets"]["a"]

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            create_joint_visit(
                subordinate_user_id=outsider.id,
                outlet_id=outlet.id,
                notes=None,
                no_order_reason="No requirement",
                linked_order_id=None,
                gps_lat=outlet.gps_lat,
                gps_lng=outlet.gps_lng,
                image=None,
                current_user=manager,
                db=db_session,
            )
        )
    assert exc.value.status_code == 403

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            create_joint_visit(
                subordinate_user_id=subordinate.id,
                outlet_id=outlet.id,
                notes=None,
                no_order_reason=None,
                linked_order_id=None,
                gps_lat=outlet.gps_lat,
                gps_lng=outlet.gps_lng,
                image=None,
                current_user=manager,
                db=db_session,
            )
        )
    assert exc.value.status_code == 400

    result = asyncio.run(
        create_joint_visit(
            subordinate_user_id=subordinate.id,
            outlet_id=outlet.id,
            notes=None,
            no_order_reason="No stock requirement",
            linked_order_id=None,
            gps_lat=outlet.gps_lat,
            gps_lng=outlet.gps_lng,
            image=None,
            current_user=manager,
            db=db_session,
        )
    )
    visit = db_session.query(VisitRecord).filter_by(id=result["id"]).one()
    assert visit.is_joint_visit is True
    assert visit.joint_with_user_id == subordinate.id
    assert visit.no_order_reason == "No stock requirement"
