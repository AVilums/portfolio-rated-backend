from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from risk_platform.config import get_settings
from risk_platform.models import Base

if context.config.config_file_name:
    fileConfig(context.config.config_file_name)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=get_settings().database_url, target_metadata=target_metadata, literal_binds=True
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(get_settings().database_url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()


run_migrations_offline() if context.is_offline_mode() else run_migrations_online()
