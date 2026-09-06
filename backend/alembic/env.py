"""Alembic okruzenje.

URL baze se uzima iz Settings (a ne iz alembic.ini) da bi vazile sigurnosne
provere: zabranjeni portovi 5432/5433 i obavezno ime baze 'foodrec'.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from backend.app.core.config import REQUIRED_DB_NAME, settings
from backend.app.db.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Settings validator je vec odbio 5432/5433 i pogresno ime baze u trenutku
# importa; ovo je jos jedna eksplicitna provera pre same migracije.
_db_name = settings.database_url.rsplit("/", 1)[-1]
if _db_name != REQUIRED_DB_NAME:
    raise RuntimeError(
        f"Alembic bi migrirao bazu {_db_name!r}, a ocekuje se {REQUIRED_DB_NAME!r}. "
        "Migracija je prekinuta."
    )

config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Migracije bez konekcije - generisu SQL na izlaz."""
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Migracije uz stvarnu konekciju na bazu."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
