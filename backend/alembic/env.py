import os
import sys
from logging.config import fileConfig
from sqlalchemy import create_engine, pool
from alembic import context
from dotenv import load_dotenv

# 1. Add the backend directory to sys.path so we can import database.py safely
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_dir)

# Now we can import your models and your cloud connector function!
from models import Base
from database import getconn

env_path = os.path.join(os.path.dirname(backend_dir), '.env')
load_dotenv(env_path)

# This is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    # Offline mode just needs a placeholder string dialect to generate SQL files
    context.configure(
        url="postgresql+pg8000://",
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # CRITICAL FIX: Instead of building a string URL from environment variables,
    # we create the engine using your passwordless Google Cloud SQL creator function.
    connectable = create_engine(
        "postgresql+pg8000://",
        creator=getconn,
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()