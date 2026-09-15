"""Additive schema. Exact amounts are decimal strings on SQLite AND PostgreSQL."""
from sqlalchemy import String, Text, Float, Integer, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class IntegrityBase(DeclarativeBase): pass

class Intent(IntegrityBase):
    __tablename__='nova_intents'
    key: Mapped[str]=mapped_column(String(180),primary_key=True)
    fingerprint: Mapped[str]=mapped_column(String(64))
    response: Mapped[str]=mapped_column(Text)
    created_at: Mapped[float]=mapped_column(Float)

class ExactPosition(IntegrityBase):
    __tablename__='nova_exact_positions'
    position_id: Mapped[int]=mapped_column(Integer,primary_key=True)
    mint: Mapped[str]=mapped_column(String(120))
    entry: Mapped[str]=mapped_column(Text)
    initial_quantity: Mapped[str]=mapped_column(Text)
    quantity: Mapped[str]=mapped_column(Text)
    cost: Mapped[str]=mapped_column(Text)
    realized: Mapped[str]=mapped_column(Text)
    entry_fee: Mapped[str]=mapped_column(Text)
    origin: Mapped[str]=mapped_column(String(40))
    mark_at: Mapped[float|None]=mapped_column(Float,nullable=True)
    closed: Mapped[int]=mapped_column(Integer,default=0)

class Ledger(IntegrityBase):
    __tablename__='nova_ledger'
    id: Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    event_key: Mapped[str]=mapped_column(String(180),unique=True)
    position_id: Mapped[int|None]=mapped_column(Integer,nullable=True)
    phase: Mapped[str]=mapped_column(String(30))
    cash_delta: Mapped[str]=mapped_column(Text)
    quantity_delta: Mapped[str]=mapped_column(Text)
    fee: Mapped[str]=mapped_column(Text)
    pnl: Mapped[str]=mapped_column(Text)
    created_at: Mapped[float]=mapped_column(Float)

class TokenObservation(IntegrityBase):
    __tablename__='nova_observation_state'
    mint: Mapped[str]=mapped_column(String(120),primary_key=True)
    first_seen: Mapped[float]=mapped_column(Float)
    received_at: Mapped[float]=mapped_column(Float)
    source_time: Mapped[float|None]=mapped_column(Float,nullable=True)
    pair: Mapped[str]=mapped_column(String(120))
    snapshot: Mapped[str]=mapped_column(Text)
