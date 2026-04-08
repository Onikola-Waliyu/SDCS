import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("No DATABASE_URL set.")
    exit(1)

engine = create_engine(DATABASE_URL)
try:
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE transaction ADD COLUMN status VARCHAR DEFAULT 'recorded';"))
        conn.commit()
    print("Migration completed: Added 'status' column to transaction table.")
except Exception as e:
    print(f"Migration error or already applied: {e}")
