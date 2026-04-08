import os
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from dotenv import load_dotenv
from sqlmodel import Field, Session, SQLModel, create_engine

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://sdcs_user:sdcs_pass@localhost:5432/sdcs_db")
engine = create_engine(DATABASE_URL, echo=False)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class UserRole(str, Enum):
    OWNER = "OWNER"
    STAFF = "STAFF"


class UserState(str, Enum):
    AWAITING_BUSINESS_NAME = "AWAITING_BUSINESS_NAME"
    ACTIVE = "ACTIVE"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class Business(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class User(SQLModel, table=True):
    phone_number: str = Field(primary_key=True)
    business_id: Optional[int] = Field(default=None, foreign_key="business.id")
    role: UserRole = Field(default=UserRole.OWNER)
    state: UserState = Field(default=UserState.AWAITING_BUSINESS_NAME)
    pin_hash: Optional[str] = Field(default=None)
    name: Optional[str] = Field(default=None)  # Display name (owner or staff)


class Transaction(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(foreign_key="business.id")
    recorded_by: str = Field(foreign_key="user.phone_number")
    item: str
    quantity: float = Field(default=1)
    unit: str = Field(default="unit")
    amount: float
    customer: Optional[str] = Field(default=None)
    status: str = Field(default="recorded")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_session():
    with Session(engine) as session:
        yield session


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
