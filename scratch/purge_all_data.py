from sqlalchemy import text
from app.database import SessionLocal
from app.utils.beat_types import seed_default_beat_types
from db_migrate import run_migrations

def purge_all_data():
    db = SessionLocal()
    try:
        tables = [row[0] for row in db.execute(text("SHOW TABLES")).fetchall()]
        print(f"Purging data from {len(tables)} tables...")
        
        db.execute(text("SET FOREIGN_KEY_CHECKS=0;"))
        for table in tables:
            db.execute(text(f"TRUNCATE TABLE `{table}`"))
        db.execute(text("SET FOREIGN_KEY_CHECKS=1;"))
        db.commit()
        print("All database tables truncated successfully.")
        
        seed_default_beat_types(db)
        run_migrations()
        print("Database reset completed successfully.")
    finally:
        db.close()

if __name__ == "__main__":
    purge_all_data()
