from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.infrastructure.settings import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def check_db_connection() -> str:
    """Returns 'ok' or 'fail' — used by the /health route."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return "ok"
    except Exception as e:
        print(f"DB connection failed: {e}")
        return "fail"