"""Alembic environment — reads DATABASE_URL from .env so it targets the same
Supabase PostgreSQL instance as Django."""

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Make project root importable so decouple can find .env
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from decouple import config as env_config

# Alembic Config object from alembic.ini
config = context.config

# Override sqlalchemy.url from environment
database_url = env_config(
    "DATABASE_URL",
    default=(
        "postgresql://{user}:{password}@{host}:{port}/{name}".format(
            user=env_config("DB_USER", default="postgres"),
            password=env_config("DB_PASSWORD", default=""),
            host=env_config("DB_HOST", default="localhost"),
            port=env_config("DB_PORT", default="5432"),
            name=env_config("DB_NAME", default="postgres"),
        )
    ),
)
config.set_main_option("sqlalchemy.url", database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import SQLAlchemy metadata from the models module if you want autogenerate.
# For Django-managed tables we keep target_metadata=None so Alembic only runs
# hand-written migrations in alembic/versions/.
target_metadata = None


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
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
