"""Alembic migration environment.

Reuses the application's synchronous engine and Base.metadata so that
autogenerate compares against the real ORM models. All model modules are
imported explicitly (mirroring app/main.py) because app/models/__init__.py
does not re-export every model class.
"""

# Ensure config validation does not block CLI alembic commands
# (validate_settings() requires JWT_SECRET_KEY; mark this as a test context).
from logging.config import fileConfig
import os

from alembic import context

os.environ.setdefault("TESTING", "true")

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import the app's engine + Base, then explicitly import every model module
# so all tables register into Base.metadata (models/__init__.py is incomplete).
from app.database import Base, engine
import app.models.knowledge
import app.models.notification
import app.models.paper_template
import app.models.paper_version
import app.models.password_reset
import app.models.question
import app.models.system_setting
import app.models.user

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Emits SQL to stdout without a live DB connection.
    """
    url = config.get_main_option("sqlalchemy.url") or str(engine.url)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode using the app's sync engine."""
    connectable = engine

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
