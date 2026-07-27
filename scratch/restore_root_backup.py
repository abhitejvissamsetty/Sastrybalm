import os
from sqlalchemy import text
from app.database import SessionLocal
from app.utils.backup_service import restore_sql_backup

def run_restore():
    sql_path = "/Users/johnwesleygovada/Desktop/Safar/safar_sfa_backup_20260725_115253.sql"
    if not os.path.exists(sql_path):
        print(f"Error: Backup file '{sql_path}' not found.")
        return

    print(f"Restoring database from root backup file: {sql_path}")
    restore_sql_backup(sql_path)
    
    db = SessionLocal()
    try:
        tables = [row[0] for row in db.execute(text("SHOW TABLES")).fetchall()]
        print(f"Database successfully restored! Total tables: {len(tables)}")
        for t in ["users", "geographies", "warehouses", "products", "beats", "outlets", "orders"]:
            if t in tables:
                cnt = db.execute(text(f"SELECT COUNT(*) FROM `{t}`")).scalar()
                print(f" - Table `{t}`: {cnt} records")
    finally:
        db.close()

if __name__ == "__main__":
    run_restore()
