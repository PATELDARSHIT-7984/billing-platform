"""Durable migration provenance; no public write authority."""
from sqlalchemy import Column, String, Integer, DateTime, JSON, CheckConstraint, ForeignKeyConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from api.config.database import Base


class LegacyAccountMap(Base):
    __tablename__ = 'legacy_account_map'
    __table_args__ = (
        CheckConstraint("legacy_source IN ('customer','party')", name='ck_legacy_account_source'),
        ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='RESTRICT', onupdate='RESTRICT'),
        ForeignKeyConstraint(['account_id', 'account_role'], ['account_roles.account_id', 'account_roles.role'],
                             name='fk_legacy_map_role', ondelete='RESTRICT', onupdate='RESTRICT'),
        ForeignKeyConstraint(['account_ledger_id', 'account_id', 'account_role'],
                             ['account_ledgers.id', 'account_ledgers.account_id', 'account_ledgers.role'],
                             name='fk_legacy_map_ledger', ondelete='RESTRICT', onupdate='RESTRICT'),
    )
    legacy_source = Column(String(20), primary_key=True)
    legacy_id = Column(Integer, primary_key=True)
    account_id = Column(Integer, nullable=False)
    account_role = Column(String(20), nullable=False)
    account_ledger_id = Column(Integer, nullable=False)
    legacy_code = Column(String(30), nullable=False)
    migration_revision = Column(String(32), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    source_snapshot = Column(JSON().with_variant(JSONB, 'postgresql'), nullable=False)
