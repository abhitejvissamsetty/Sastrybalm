from decimal import Decimal

import pytest

from app.models.order import (
    Order,
    OrderItem,
    OrderStatus,
    OrderType,
    PaymentSettlementStatus,
)
from app.models.payment import Payment, PaymentStatus
from app.models.product_warehouse import ProductWarehouseStock
from app.services.native_operations_service import confirm_order_natively


def _company_order(db, acceptance, *, number="ACC-PRIMARY-0001", quantity=2):
    order = Order(
        order_number=number,
        channel_partner=acceptance["partners"]["a"],
        party_id=acceptance["partners"]["a"].id,
        party_type="Channel Partner",
        user=acceptance["users"]["l3"],
        warehouse=acceptance["warehouses"]["a"],
        company_profile=acceptance["company"],
        order_type=OrderType.primary,
        is_company_order=True,
        payment_type="Credit",
        status=OrderStatus.submitted,
    )
    order.items.append(
        OrderItem(
            product=acceptance["products"]["sales"],
            quantity=quantity,
            unit_price=118,
            gst_rate=18,
        )
    )
    db.add(order)
    db.commit()
    return order


def test_primary_order_confirmation_deducts_stock_exactly_once(
    db_session, acceptance_data, monkeypatch
):
    monkeypatch.setattr(
        "app.services.channel_partner_notification.trigger_instant_order_notification",
        lambda *_: None,
    )
    order = _company_order(db_session, acceptance_data)
    assert order.subtotal == 200
    assert order.total_gst == 36
    assert order.total_amount == 236
    stock = db_session.query(ProductWarehouseStock).filter_by(
        product_id=acceptance_data["products"]["sales"].id,
        warehouse_id=acceptance_data["warehouses"]["a"].id,
    ).one()
    initial = stock.stock_qty

    confirm_order_natively(order, db_session)
    db_session.refresh(stock)
    assert order.status == OrderStatus.confirmed
    assert stock.stock_qty == initial - 2

    confirm_order_natively(order, db_session)
    db_session.refresh(stock)
    assert stock.stock_qty == initial - 2


def test_insufficient_stock_rolls_back_order_confirmation(
    db_session, acceptance_data, monkeypatch
):
    monkeypatch.setattr(
        "app.services.channel_partner_notification.trigger_instant_order_notification",
        lambda *_: None,
    )
    order = _company_order(
        db_session, acceptance_data, number="ACC-PRIMARY-0002", quantity=101
    )
    with pytest.raises(ValueError, match="Insufficient stock"):
        confirm_order_natively(order, db_session)
    db_session.rollback()
    db_session.refresh(order)
    assert order.status == OrderStatus.submitted


def test_secondary_order_totals_and_payment_settlement(operational_data):
    order = operational_data["order"]
    assert order.order_type == OrderType.secondary
    assert order.subtotal == 500
    assert order.total_gst == 90
    assert order.total_amount == 590
    assert order.total_paid == 590
    assert order.balance_due == 0

    order.payment_settlement = PaymentSettlementStatus.paid
    assert order.payment_settlement == PaymentSettlementStatus.paid
