import os
import time
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from app.config import settings

# Force system process environment timezone to IST (Asia/Kolkata)
os.environ["TZ"] = "Asia/Kolkata"
if hasattr(time, "tzset"):
    time.tzset()

engine_kwargs = {
    "pool_pre_ping": True,
    "echo": False,
    "pool_recycle": 3600,
    "pool_size": 10,
    "max_overflow": 20,
}

engine = create_engine(settings.db_url, **engine_kwargs)


@event.listens_for(engine, "connect")
def set_mysql_timezone(dbapi_connection, connection_record):
    """Enforces GMT+05:30 (IST) session timezone on every database connection."""
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("SET time_zone = '+05:30';")
        cursor.close()
    except Exception:
        pass


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
