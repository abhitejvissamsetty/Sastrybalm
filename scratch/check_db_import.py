from app.database import engine
from sqlalchemy import inspect, text

def check():
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print("--- IMPORTED STAGING TABLES & ROW COUNTS ---")
    with engine.connect() as conn:
        for t in sorted(tables):
            cnt = conn.execute(text(f"SELECT COUNT(*) FROM `{t}`")).scalar()
            print(f" - {t}: {cnt} rows")

if __name__ == "__main__":
    check()
