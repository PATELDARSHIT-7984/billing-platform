"""Global account GSTIN identity; abort on conflicting or invalid legacy data.

Revision ID: e9a41c8d720b
Revises: c4a9e7120d35
"""
from alembic import op
import sqlalchemy as sa

revision = "e9a41c8d720b"
down_revision = "c4a9e7120d35"
branch_labels = None
depends_on = None

# Freeze migration normalization here; future application changes must not change
# the meaning of an already released migration. No checksum validation is added.
NORMALIZED = r"NULLIF(upper(regexp_replace(gstin, '^\s+|\s+$', '', 'g')), '')"
IDENTITIES = f"""
    SELECT 'customer' AS source, id, {NORMALIZED} AS gstin FROM customers
    UNION ALL
    SELECT 'party' AS source, id, {NORMALIZED} AS gstin FROM parties
"""


def upgrade():
    connection = op.get_bind()
    # Prevent an account write between preflight and backfill. PostgreSQL DDL
    # and this data backfill roll back together if any step fails.
    connection.execute(sa.text("LOCK TABLE customers, parties IN SHARE ROW EXCLUSIVE MODE"))
    conflicts = connection.execute(sa.text(f"""
        WITH identities AS ({IDENTITIES})
        SELECT gstin, string_agg(source || ':' || id::text, ', ' ORDER BY source, id) AS owners
        FROM identities WHERE gstin IS NOT NULL GROUP BY gstin HAVING count(*) > 1
        ORDER BY gstin LIMIT 20
    """)).all()
    if conflicts:
        raise RuntimeError(f"GSTIN backfill stopped: conflicting account identities (up to 20): {conflicts}")
    invalid = connection.execute(sa.text(f"""
        WITH identities AS ({IDENTITIES})
        SELECT source, id FROM identities WHERE gstin IS NOT NULL
        AND gstin !~ '^[0-9]{{2}}[A-Z]{{5}}[0-9]{{4}}[A-Z][A-Z0-9]Z[A-Z0-9]$'
        ORDER BY source, id LIMIT 20
    """)).all()
    if invalid:
        raise RuntimeError(f"GSTIN backfill stopped: invalid account GSTINs (up to 20): {invalid}")
    op.create_table("account_gstin_registry",
        sa.Column("account_source", sa.String(30), primary_key=True),
        sa.Column("account_id", sa.Integer(), primary_key=True),
        sa.Column("normalized_gstin", sa.String(15), nullable=False),
        sa.UniqueConstraint("normalized_gstin", name="uq_account_gstin"))
    for table in ("customers", "parties"):
        connection.execute(sa.text(f"UPDATE {table} SET gstin = {NORMALIZED} WHERE gstin IS DISTINCT FROM {NORMALIZED}"))
    connection.execute(sa.text(f"""
        INSERT INTO account_gstin_registry (account_source, account_id, normalized_gstin)
        SELECT source, id, gstin FROM ({IDENTITIES}) AS identities
        WHERE gstin IS NOT NULL ORDER BY source, id
    """))


def downgrade():
    # Canonical spellings are retained; only the registry is removed.
    op.drop_table("account_gstin_registry")
