"""How Alembic reaches the database.

The app runs migrations itself when it opens the database (db.migrate), giving
Alembic its connection. The `alembic` command (see alembic.ini) uses the same
database as the app: DATABASE_URL from .env or the environment, or the SQLite
file in the project folder.
"""

from logging.config import fileConfig

from alembic import context

from price_tracker import db, envfile
from price_tracker.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
if config.attributes.get("connection") is None:
    envfile.load()      # run as the `alembic` command, not by the app


def run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        # SQLite can't change most columns in place; batch mode copies the table instead.
        render_as_batch=connection.dialect.name == "sqlite",
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(url=str(db.database_url()), target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
elif (connection := config.attributes.get("connection")) is not None:
    run_migrations(connection)
else:
    engine = db.make_engine(upgrade=False)
    with engine.begin() as connection:
        run_migrations(connection)
    engine.dispose()
