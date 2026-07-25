import os
from sqlalchemy import text
from app.database import SessionLocal
from app.utils.beat_types import seed_default_beat_types
from db_migrate import run_migrations

def clear_all_data():
    db = SessionLocal()
    try:
        tables = [row[0] for row in db.execute(text("SHOW TABLES")).fetchall()]
        print(f"Found {len(tables)} tables to clear.")
        
        db.execute(text("SET FOREIGN_KEY_CHECKS=0;"))
        for table in tables:
            db.execute(text(f"TRUNCATE TABLE `{table}`"))
            print(f"Truncated table: {table}")
            
        db.execute(text("SET FOREIGN_KEY_CHECKS=1;"))
        db.commit()
        print("All tables successfully cleared.")
        
        # Seed default beat types master
        seed_default_beat_types(db)
        
        # Run migrations
        run_migrations()
        
        print("DATABASE RESET COMPLETED SUCCESSFULLY!")
    finally:
        db.close()

if __name__ == "__main__":
    clear_all_data()
