"""
Shared pytest fixtures for the SDCS test suite.
Uses an in-memory SQLite database so tests never touch PostgreSQL.
"""
import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.db.models import Transaction


@pytest.fixture(name="engine", scope="session")
def engine_fixture():
    """Single in-memory SQLite engine for the full test session."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture(name="session")
def session_fixture(engine):
    """Fresh session per test; rolls back after each test."""
    with Session(engine) as session:
        yield session


@pytest.fixture(name="sample_transaction")
def sample_transaction_fixture(session):
    """A committed sample transaction ready for use in tests."""
    tx = Transaction(
        phone_number="2348012345678",
        item="rice",
        quantity=5,
        unit="bags",
        amount=200000,
        customer="Hilary",
    )
    session.add(tx)
    session.commit()
    session.refresh(tx)
    return tx
