"""Automated database schema synchronization and self-healing.

Ensures that incremental schema updates (such as newly added columns and sequences)
are seamlessly applied on application startup across PostgreSQL and SQLite
even if migrations have not yet been manually executed.
"""
import logging
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def sync_database_schema(engine: Engine) -> None:
    """Ensure database schema is compatible with current application models."""
    try:
        with engine.begin() as conn:
            inspector = inspect(conn)
            table_names = set(inspector.get_table_names())
            dialect_name = conn.dialect.name

            # 1. quotations table compatibility
            if "quotations" in table_names:
                cols = {c["name"] for c in inspector.get_columns("quotations")}
                if "customer_name" not in cols:
                    if dialect_name == "postgresql":
                        conn.execute(text("ALTER TABLE quotations ADD COLUMN IF NOT EXISTS customer_name VARCHAR(255);"))
                    else:
                        conn.execute(text("ALTER TABLE quotations ADD COLUMN customer_name VARCHAR(255);"))
                    logger.info("Added missing column quotations.customer_name")

                if dialect_name == "postgresql":
                    try:
                        conn.execute(text("ALTER TABLE quotations ALTER COLUMN customer_id DROP NOT NULL;"))
                    except Exception as e:
                        logger.debug("Could not alter quotations.customer_id nullability: %s", e)

            # 2. item_master igst compatibility
            if "item_master" in table_names:
                cols = {c["name"] for c in inspector.get_columns("item_master")}
                if "igst" not in cols:
                    if dialect_name == "postgresql":
                        conn.execute(text("ALTER TABLE item_master ADD COLUMN IF NOT EXISTS igst NUMERIC(5, 2) DEFAULT 0.00;"))
                    else:
                        conn.execute(text("ALTER TABLE item_master ADD COLUMN igst NUMERIC(5, 2) DEFAULT 0.00;"))
                    logger.info("Added missing column item_master.igst")

            # 3. account_code_seq sequence for PostgreSQL
            if dialect_name == "postgresql":
                try:
                    conn.execute(text("CREATE SEQUENCE IF NOT EXISTS account_code_seq START WITH 100 INCREMENT BY 1;"))
                except Exception as e:
                    logger.debug("Could not create account_code_seq: %s", e)

    except Exception as exc:
        logger.warning("Database schema auto-sync encountered an error (continuing): %s", exc)

