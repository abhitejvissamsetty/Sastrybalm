import asyncio
from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile

from app.models.asset_capitalization import AssetCapitalization
from app.models.idempotency import IdempotencyRecord
from app.models.material_request import MaterialRequest
from app.models.order import Order
from app.models.payment import Payment
from app.models.product import Product, ProductCategory
from app.models.product_warehouse import ProductWarehouseStock
from app.models.timesheet import VisitRecord
from app.routers.api.operations import (
    collect_payment,
    create_asset_capitalization_api,
    create_order,
    log_visit,
    submit_material_request,
)


def test_mobile_mutation_replays_once_and_rejects_key_reuse(
    db_session, acceptance_data, monkeypatch
):
    monkeypatch.setattr("app.services.auto_flagging.flag_visit_gps", lambda *_: None)
    rep = acceptance_data["users"]["l1"]
    outlet = acceptance_data["outlets"]["a"]
    arguments = dict(
        outlet_id=outlet.id,
        gps_lat=outlet.gps_lat,
        gps_lng=outlet.gps_lng,
        purpose="Idempotency acceptance",
        notes=None,
        idempotency_key="visit-idempotency-0001",
        current_user=rep,
        db=db_session,
    )

    first = asyncio.run(log_visit(**arguments))
    second = asyncio.run(log_visit(**arguments))
    assert second == first
    assert db_session.query(VisitRecord).filter_by(id=first["id"]).count() == 1
    assert db_session.query(IdempotencyRecord).count() == 1

    with pytest.raises(HTTPException) as exc:
        asyncio.run(log_visit(**{**arguments, "gps_lat": outlet.gps_lat + 1}))
    assert exc.value.status_code == 409


def test_failed_mutation_releases_key_for_corrected_retry(
    db_session, acceptance_data, monkeypatch
):
    monkeypatch.setattr("app.services.auto_flagging.flag_visit_gps", lambda *_: None)
    rep = acceptance_data["users"]["l1"]
    outlet = acceptance_data["outlets"]["a"]
    arguments = dict(
        outlet_id=outlet.id,
        gps_lat=91,
        gps_lng=outlet.gps_lng,
        purpose=None,
        notes=None,
        idempotency_key="visit-idempotency-retry",
        current_user=rep,
        db=db_session,
    )
    with pytest.raises(HTTPException):
        asyncio.run(log_visit(**arguments))
    assert db_session.query(IdempotencyRecord).count() == 0

    result = asyncio.run(
        log_visit(**{**arguments, "gps_lat": outlet.gps_lat})
    )
    assert result["id"]
    assert db_session.query(IdempotencyRecord).count() == 1


def test_duplicate_order_and_payment_submissions_replay_without_side_effects(
    db_session, acceptance_data, monkeypatch
):
    monkeypatch.setattr("app.services.auto_flagging.flag_visit_gps", lambda *_: None)
    monkeypatch.setattr(
        "app.services.auto_flagging.flag_payment_mismatch", lambda *_: None
    )
    rep = acceptance_data["users"]["l1"]
    outlet = acceptance_data["outlets"]["a"]
    product = acceptance_data["products"]["sales"]
    visit = asyncio.run(
        log_visit(
            outlet_id=outlet.id,
            gps_lat=outlet.gps_lat,
            gps_lng=outlet.gps_lng,
            purpose="Idempotent order",
            notes=None,
            idempotency_key="duplicate-order-visit",
            current_user=rep,
            db=db_session,
        )
    )
    order_args = dict(
        items=[
            {
                "product_id": product.id,
                "quantity": 1,
                "unit_price": 100,
                "gst_rate": 18,
                "discount_pct": 0,
            }
        ],
        outlet_id=outlet.id,
        visit_id=visit["id"],
        idempotency_key="duplicate-order",
        current_user=rep,
        db=db_session,
    )
    first_order = asyncio.run(create_order(**order_args))
    assert asyncio.run(create_order(**order_args)) == first_order
    assert db_session.query(Order).count() == 1

    payment_args = dict(
        outlet_id=outlet.id,
        order_id=first_order["id"],
        amount=118,
        method="cash",
        idempotency_key="duplicate-payment",
        current_user=rep,
        db=db_session,
    )
    first_payment = asyncio.run(collect_payment(**payment_args))
    assert asyncio.run(collect_payment(**payment_args)) == first_payment
    assert db_session.query(Payment).count() == 1


def test_duplicate_material_request_replays_without_uploading_twice(
    db_session, acceptance_data, monkeypatch
):
    uploads = []

    async def store(_db, upload, prefix):
        uploads.append(prefix)
        return f"s3://acceptance/{prefix}/{upload.filename}"

    monkeypatch.setattr(
        "app.routers.api.operations._store_required_image", store
    )
    rep = acceptance_data["users"]["l1"]
    outlet = acceptance_data["outlets"]["a"]
    product = acceptance_data["products"]["marketing"]
    args = dict(
        outlet_id=outlet.id,
        product_id=product.id,
        description="Duplicate-safe signage request",
        dimension_length=None,
        dimension_width=None,
        dimension_height=None,
        dimension_depth=None,
        dimension_unit="cm",
        present_outlet_image=UploadFile(
            filename="present.jpg", file=BytesIO(b"present")
        ),
        installation_place_image=UploadFile(
            filename="installation.jpg", file=BytesIO(b"installation")
        ),
        customer_approval_letter_image=UploadFile(
            filename="approval.jpg", file=BytesIO(b"approval")
        ),
        idempotency_key="duplicate-material-request",
        current_user=rep,
        db=db_session,
    )
    first = asyncio.run(submit_material_request(**args))
    assert asyncio.run(submit_material_request(**args)) == first
    assert db_session.query(MaterialRequest).count() == 1
    assert len(uploads) == 3


def test_duplicate_asset_submission_deducts_inventory_once(
    db_session, acceptance_data
):
    product = Product(
        name="Idempotent Marketing Stock",
        sku="ACC-IDEMP-ASSET",
        category_type=ProductCategory.marketing_stock,
        is_active=True,
        warehouse=acceptance_data["warehouses"]["a"],
    )
    stock = ProductWarehouseStock(
        product=product,
        warehouse=acceptance_data["warehouses"]["a"],
        stock_qty=3,
        is_active=True,
    )
    db_session.add_all([product, stock])
    db_session.commit()
    args = dict(
        outlet_id=acceptance_data["outlets"]["a"].id,
        product_id=product.id,
        quantity=1,
        notes="Duplicate-safe deployment",
        image=None,
        idempotency_key="duplicate-asset",
        current_user=acceptance_data["users"]["l3"],
        db=db_session,
    )
    first = asyncio.run(create_asset_capitalization_api(**args))
    assert asyncio.run(create_asset_capitalization_api(**args)) == first
    db_session.refresh(stock)
    assert stock.stock_qty == 2
    assert db_session.query(AssetCapitalization).count() == 1
