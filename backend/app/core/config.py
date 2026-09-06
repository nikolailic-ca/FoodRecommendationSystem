"""Aplikaciona konfiguracija ucitana iz .env fajla u korenu projekta.

Validatori u ovoj datoteci su sigurnosna mreza: sprecavaju da se aplikacija
ikada poveze na pogresnu bazu (vidi FORBIDDEN_PORTS i REQUIRED_DB_NAME).
"""

from functools import lru_cache
from pathlib import Path
from typing import Annotated
from urllib.parse import unquote, urlsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# backend/app/core/config.py -> backend/app/core -> backend/app -> backend -> koren
PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = PROJECT_ROOT / ".env"

# 5432 je AWS SSM tunel ka PRODUKCIJSKOJ RDS bazi drugog projekta.
# 5433 koriste tri druga lokalna projekta. Ovaj projekat koristi 15432.
FORBIDDEN_PORTS = {5432, 5433}
REQUIRED_DB_NAME = "foodrec"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        # Dozvoljava polje model_artifact_dir (pydantic po defaultu cuva 'model_' prefiks).
        protected_namespaces=(),
    )

    # Bez default vrednosti: ako nedostaju, aplikacija pada pri startu.
    database_url: str
    jwt_secret: str

    jwt_expires_days: int = 7
    # NoDecode: sprecava pydantic-settings da vrednost pokusa da procita kao JSON,
    # pa validator ispod moze da razdvoji obican "a,b" string.
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5180",
        "http://127.0.0.1:5180",
    ]
    pexels_api_key: str = ""
    model_artifact_dir: str = "ai/artifacts/mult_vae"
    onboarding_min_ratings: int = 5
    positive_rating_threshold: int = 4

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        """Prihvata 'a,b,c' string iz .env i pretvara ga u listu."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("database_url")
    @classmethod
    def _validate_database_url(cls, value: str) -> str:
        # SQLAlchemy DSN oblik: postgresql+psycopg://user:pass@host:port/dbname
        parsed = urlsplit(value)

        try:
            port = parsed.port
        except ValueError as exc:  # neparsabilan port
            raise ValueError(f"DATABASE_URL ima neispravan port: {exc}") from exc

        if port in FORBIDDEN_PORTS:
            raise ValueError(
                f"DATABASE_URL koristi zabranjen port {port}. "
                "Port 5432 je AWS SSM tunel ka PRODUKCIJSKOJ RDS bazi drugog projekta, "
                "a 5433 koriste ostali lokalni projekti. "
                "Ovaj projekat koristi Postgres na 127.0.0.1:15432 "
                "(vidi docker-compose.yml i .env.example)."
            )

        db_name = unquote(parsed.path).lstrip("/")
        if db_name != REQUIRED_DB_NAME:
            raise ValueError(
                f"DATABASE_URL pokazuje na bazu {db_name!r}, a ocekuje se "
                f"{REQUIRED_DB_NAME!r}. Provera sprecava pisanje u tudju bazu."
            )

        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
