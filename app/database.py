from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings

engine_kwargs = {
    "pool_pre_ping": True,
    "echo": False,
}

if settings.db_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_recycle"] = 3600
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20

engine = create_engine(settings.db_url, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
