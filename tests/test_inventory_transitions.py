import pytest
from sqlalchemy.exc import IntegrityError

from app.models.product_warehouse import ProductWarehouseStock
from app.services.inventory_service import record_stock_movement


def test_inventory_inward_outward_adjustment_and_insufficient_stock(
    db_session, acceptance_data
):
    product = acceptance_data["products"]["sales"]
    warehouse = acceptance_data["warehouses"]["a"]
    stock = next(
        row
        for row in product.warehouse_stocks
        if row.warehouse_id == warehouse.id
    )

    record_stock_movement(
        db_session, product.id, "INWARD", 10, warehouse_id=warehouse.id
    )
    assert stock.stock_qty == 110

    record_stock_movement(
        db_session, product.id, "OUTWARD", 15, warehouse_id=warehouse.id
    )
    assert stock.stock_qty == 95

    record_stock_movement(
        db_session, product.id, "ADJUSTMENT", 80, warehouse_id=warehouse.id
    )
    assert stock.stock_qty == 80

    with pytest.raises(ValueError, match="Insufficient stock"):
        record_stock_movement(
            db_session, product.id, "OUTWARD", 81, warehouse_id=warehouse.id
        )
    assert stock.stock_qty == 80


def test_stock_balance_is_unique_per_product_and_warehouse(
    db_session, acceptance_data
):
    db_session.add(
        ProductWarehouseStock(
            product=acceptance_data["products"]["sales"],
            warehouse=acceptance_data["warehouses"]["a"],
            stock_qty=1,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
