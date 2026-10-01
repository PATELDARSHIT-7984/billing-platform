import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from sqlalchemy.engine import make_url

from alembic import context

# Makes the `api` package importable regardless of which directory
# `alembic` is invoked from -- env.py's own folder is normally
# <project_root>/alembic, so its parent is the project root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Base is the declarative base every model inherits from (api/config/database.py).
# DATABASE_URL is imported too so alembic always uses the same connection
# string as the running app -- no separate copy to keep in sync inside alembic.ini.
from api.config.database import Base, DATABASE_URL

# Importing every model module registers its table on Base.metadata.
# Nothing below needs to be used directly -- the import side effect is
# the whole point, and this is the one place that has to know every
# model file that exists so "alembic revision --autogenerate" can see
# every table when generating a migration.
from api.model.bank import BankModel  
from api.model.bill import Bill
from api.model.bill_item import BillItem  
from api.model.company_profile import CompanyProfile  
from api.model.customer import Customer
from api.model.done_by import DoneByModel
from api.model.item_master import ItemMaster
from api.model.party import Party
from api.model.purchase import Purchase,PurchaseItem
from api.model.purchase_return import PurchaseReturn,PurchaseReturnItem
from api.model.quotation import Quotation,QuotationItem
from api.model.rojmel import Rojmel
from api.model.sales_return import SalesReturn,SalesReturnItem

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Use the application's connection settings. An explicit database-name override
# allows disposable bootstrap verification without touching the development DB.
database_name = context.get_x_argument(as_dictionary=True).get("database")
database_url = make_url(DATABASE_URL)
if database_name:
    database_url = database_url.set(database=database_name)
config.set_main_option("sqlalchemy.url", database_url.render_as_string(hide_password=False).replace("%", "%%"))

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# target_metadata drives autogenerate -- it now points at every table
# registered on Base by the imports above, instead of nothing.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
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
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
