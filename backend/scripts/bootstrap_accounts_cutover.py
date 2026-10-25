"""Bootstrap accounts tables, columns, constraints, and legacy backfill for PostgreSQL."""
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import text
from api.config.database import engine, SessionLocal
from api.model.customer import Customer
from api.model.party import Party
from api.model.legacy_account_map import LegacyAccountMap
from api.services.account_provisioning import provision_legacy_account


def run_bootstrap():
    with engine.begin() as conn:
        print("1. Adding missing columns and constraints to accounts...")
        conn.execute(text("ALTER TABLE accounts ADD COLUMN IF NOT EXISTS gstin_pending BOOLEAN NOT NULL DEFAULT false;"))
        conn.execute(text("CREATE SEQUENCE IF NOT EXISTS account_code_seq START WITH 100 INCREMENT BY 1;"))

        print("2. Ensuring unique constraints on account_ledgers...")
        conn.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_account_ledgers_identity') THEN
                    ALTER TABLE account_ledgers ADD CONSTRAINT uq_account_ledgers_identity UNIQUE (id, account_id, role);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_account_ledgers_id_role') THEN
                    ALTER TABLE account_ledgers ADD CONSTRAINT uq_account_ledgers_id_role UNIQUE (id, role);
                END IF;
            END $$;
        """))

        print("3. Creating legacy_account_map table if not exists...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS legacy_account_map (
                legacy_source VARCHAR(20) NOT NULL,
                legacy_id INTEGER NOT NULL,
                account_id INTEGER NOT NULL,
                account_role VARCHAR(20) NOT NULL,
                account_ledger_id INTEGER NOT NULL,
                legacy_code VARCHAR(30) NOT NULL,
                migration_revision VARCHAR(32) NOT NULL,
                created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now(),
                source_snapshot JSONB NOT NULL,
                PRIMARY KEY (legacy_source, legacy_id),
                CONSTRAINT ck_legacy_account_source CHECK (legacy_source IN ('customer', 'party')),
                CONSTRAINT fk_legacy_map_account FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE RESTRICT ON UPDATE RESTRICT,
                CONSTRAINT fk_legacy_map_role FOREIGN KEY (account_id, account_role) REFERENCES account_roles(account_id, role) ON DELETE RESTRICT ON UPDATE RESTRICT,
                CONSTRAINT fk_legacy_map_ledger FOREIGN KEY (account_ledger_id, account_id, account_role) REFERENCES account_ledgers(id, account_id, role) ON DELETE RESTRICT ON UPDATE RESTRICT
            );
        """))

        print("4. Adding reference columns to transaction tables...")
        for table in ["bill", "sales_returns", "purchases", "purchase_returns", "rojmel"]:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS account_ledger_id INTEGER;"))
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS account_role VARCHAR(20);"))
        conn.execute(text("ALTER TABLE quotations ADD COLUMN IF NOT EXISTS account_id INTEGER;"))

    print("5. Backfilling existing customers and parties...")
    db = SessionLocal()
    try:
        customers = db.query(Customer).all()
        parties = db.query(Party).all()
        for c in customers:
            existing = db.get(LegacyAccountMap, ("customer", c.id))
            if not existing:
                print(f"  Provisioning customer {c.id}: {c.customer_name}")
                provision_legacy_account(db, "customer", c)
            else:
                print(f"  Customer {c.id} already mapped to account {existing.account_id}")

        for p in parties:
            existing = db.get(LegacyAccountMap, ("party", p.id))
            if not existing:
                print(f"  Provisioning party {p.id}: {p.name}")
                provision_legacy_account(db, "party", p)
            else:
                print(f"  Party {p.id} already mapped to account {existing.account_id}")

        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

    with engine.begin() as conn:
        print("6. Linking existing transactions to new ledgers...")
        conn.execute(text("""
            UPDATE bill b SET account_ledger_id = m.account_ledger_id, account_role = m.account_role
            FROM legacy_account_map m WHERE m.legacy_source = 'customer' AND m.legacy_id = b.customer_id
            AND b.account_ledger_id IS NULL;

            UPDATE sales_returns sr SET account_ledger_id = m.account_ledger_id, account_role = m.account_role
            FROM legacy_account_map m WHERE m.legacy_source = 'customer' AND m.legacy_id = sr.customer_id
            AND sr.account_ledger_id IS NULL;

            UPDATE purchases p SET account_ledger_id = m.account_ledger_id, account_role = m.account_role
            FROM legacy_account_map m WHERE m.legacy_source = 'party' AND m.legacy_id = p.party_id
            AND p.account_ledger_id IS NULL;

            UPDATE purchase_returns pr SET account_ledger_id = m.account_ledger_id, account_role = m.account_role
            FROM legacy_account_map m WHERE m.legacy_source = 'party' AND m.legacy_id = pr.party_id
            AND pr.account_ledger_id IS NULL;

            UPDATE rojmel r SET account_ledger_id = m.account_ledger_id, account_role = m.account_role
            FROM legacy_account_map m WHERE m.legacy_source = 'customer' AND m.legacy_id = r.customer_id
            AND r.account_ledger_id IS NULL;

            UPDATE rojmel r SET account_ledger_id = m.account_ledger_id, account_role = m.account_role
            FROM legacy_account_map m WHERE m.legacy_source = 'party' AND m.legacy_id = r.party_id
            AND r.account_ledger_id IS NULL;

            UPDATE quotations q SET account_id = m.account_id
            FROM legacy_account_map m WHERE m.legacy_source = 'customer' AND m.legacy_id = q.customer_id
            AND q.account_id IS NULL;
        """))

        print("7. Updating alembic_version to d6e83f2a910c...")
        conn.execute(text("UPDATE alembic_version SET version_num = 'd6e83f2a910c';"))

    print("Bootstrap completed successfully!")


if __name__ == '__main__':
    run_bootstrap()

