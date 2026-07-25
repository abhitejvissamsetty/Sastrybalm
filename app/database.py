from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings

engine_kwargs = {
    "pool_pre_ping": True,
    "echo": False,
    "pool_recycle": 3600,
    "pool_size": 10,
    "max_overflow": 20,
}

engine = create_engine(settings.db_url, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
