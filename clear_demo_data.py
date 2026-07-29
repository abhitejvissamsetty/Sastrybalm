#!/usr/bin/env python3
"""
Utility script to wipe out all demo transactional data (Orders, Visits, Payments, Expenses, Leaves, Material Requests, Timesheets, Assets)
while preserving system configuration and master tables.
"""
from sqlalchemy import text
from app.database import SessionLocal

TRANSACTION_TABLES = [
    "orders",
    "order_items",
    "payments",
    "payment_submissions",
    "payment_submission_items",
    "visits",
    "expenses",
    "leaves",
    "material_requests",
    "material_request_history_logs",
    "timesheets",
    "asset_capitalizations",
    "alerts",
    "stock_movements",
    "vendor_quotations",
    "work_orders",
]

def clear_demo_data():
    db = SessionLocal()
    try:
        print("Clearing demo transactional data...")
        db.execute(text("SET FOREIGN_KEY_CHECKS=0;"))
        for table in TRANSACTION_TABLES:
            try:
                db.execute(text(f"TRUNCATE TABLE `{table}`"))
                print(f"  ✓ Truncated {table}")
            except Exception as e:
                print(f"  ! Error clearing {table}: {e}")
        db.execute(text("SET FOREIGN_KEY_CHECKS=1;"))
        db.commit()
        print("✓ All demo transactional data cleared successfully.")
    finally:
        db.close()

if __name__ == "__main__":
    clear_demo_data()
