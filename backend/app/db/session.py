"""SQLAlchemy engine, sesija i FastAPI dependency."""

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import REQUIRED_DB_NAME, settings

engine = create_engine(settings.database_url, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: jedna sesija po zahtevu."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verify_database() -> str:
    """Poslednja provera pred rad: da li smo zaista u bazi 'foodrec'.

    Podize izuzetak ako nismo - bolje pasti pri startu nego pisati u tudju bazu.
    """
    with engine.connect() as connection:
        current = connection.execute(text("SELECT current_database()")).scalar_one()

    if current != REQUIRED_DB_NAME:
        raise RuntimeError(
            f"Povezani smo na bazu {current!r}, a ocekuje se {REQUIRED_DB_NAME!r}. "
            "Provera DATABASE_URL u .env fajlu."
        )

    return current
