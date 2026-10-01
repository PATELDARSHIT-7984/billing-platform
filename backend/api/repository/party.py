from decimal import Decimal

from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session

from api.model.party import Party


def get_database_dialect_name(db: Session) -> str:
    return db.get_bind().dialect.name


def get_next_party_code_sequence_value(db: Session) -> int:
    return db.execute(text("SELECT nextval('party_code_seq')")).scalar_one()


def get_max_party_id(db: Session) -> int:
    return db.query(func.max(Party.id)).scalar() or 0


def get_party_by_id(db: Session, party_id: int) -> Party | None:
    return (
        db.query(Party)
        .filter(
            Party.id == party_id,
            Party.is_active == True,
        )
        .first()
    )


def get_party_by_id_any_status(db: Session, party_id: int) -> Party | None:
    return db.query(Party).filter(Party.id == party_id).first()


def get_party_by_gstin(
    db: Session,
    gstin: str,
    exclude_id: int | None = None,
) -> Party | None:
    # Do not filter by is_active here because gstin is UNIQUE at DB level.
    query = db.query(Party).filter(Party.gstin == gstin)

    if exclude_id is not None:
        query = query.filter(Party.id != exclude_id)

    return query.first()


def list_parties(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    search: str | None = None,
) -> list[Party]:
    query = db.query(Party).filter(Party.is_active == True)

    if search:
        query = query.filter(
            or_(
                Party.name.ilike(f"%{search}%"),
                Party.party_code.ilike(f"%{search}%"),
                Party.mobile.ilike(f"%{search}%"),
                Party.city.ilike(f"%{search}%"),
                Party.state.ilike(f"%{search}%"),
                Party.gstin.ilike(f"%{search}%"),
                Party.pan_card.ilike(f"%{search}%"),
            )
        )

    return (
        query
        .order_by(Party.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def create_party(db: Session, data: dict) -> Party:
    party = Party(**data)
    db.add(party)
    db.flush()
    return party


def update_party(db: Session, party: Party, data: dict) -> Party:
    for field_name, field_value in data.items():
        setattr(party, field_name, field_value)

    db.flush()
    return party


def set_party_current_balance(
    db: Session,
    party: Party,
    current_balance: Decimal,
    current_balance_type: str,
) -> Party:
    party.current_balance = current_balance
    party.current_balance_type = current_balance_type
    db.flush()
    return party


def deactivate_party(db: Session, party: Party) -> Party:
    party.is_active = False
    db.flush()
    return party