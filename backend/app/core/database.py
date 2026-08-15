from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

_connect_args = {}
_engine_kwargs = {"pool_pre_ping": True, "future": True}

if settings.DATABASE_URL.startswith("sqlite"):
    _connect_args["check_same_thread"] = False
    # SQLite has no pooling knobs worth setting; drop the PG-only ones.
    _engine_kwargs.pop("pool_pre_ping")
else:
    _engine_kwargs.update(pool_size=10, max_overflow=20)

engine = create_engine(settings.DATABASE_URL, connect_args=_connect_args, **_engine_kwargs)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


@event.listens_for(Engine, "connect")
def _enable_sqlite_fks(dbapi_connection, connection_record):
    """SQLite ignores FK constraints unless asked; Postgres enforces them natively."""
    if settings.DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
