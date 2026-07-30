#!/usr/bin/env python3
"""
Utility script to wipe out all demo transactional data (Orders, Visits, Payments, Expenses, Leaves, Material Requests, Timesheets, Assets)
while preserving system configuration and master tables.
"""
from sqlalchemy import inspect, text
from app.database import SessionLocal

TRANSACTION_TABLES = [
    "orders",
    "order_items",
    "payments",
    "visit_records",
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
        is_postgres = (db.bind.dialect.name == "postgresql") if db.bind else False
        existing_tables = set(inspect(db.bind).get_table_names()) if db.bind else set()

        if is_postgres:
            db.execute(text("SET session_replication_role = 'replica';"))
        else:
            db.execute(text("SET FOREIGN_KEY_CHECKS=0;"))

        for table in TRANSACTION_TABLES:
            if table not in existing_tables:
                continue
            try:
                if is_postgres:
                    db.execute(text(f'TRUNCATE TABLE "{table}" CASCADE;'))
                else:
                    db.execute(text(f"TRUNCATE TABLE `{table}`"))
                print(f"  ✓ Truncated {table}")
            except Exception as e:
                print(f"  ! Error clearing {table}: {e}")
                if is_postgres:
                    db.rollback()

        if is_postgres:
            db.execute(text("SET session_replication_role = 'origin';"))
        else:
            db.execute(text("SET FOREIGN_KEY_CHECKS=1;"))

        db.commit()
        print("✓ All demo transactional data cleared successfully.")
    finally:
        db.close()

if __name__ == "__main__":
    clear_demo_data()
