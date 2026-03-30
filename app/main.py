import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from fastapi.staticfiles import StaticFiles

from app.api.webhook import router as webhook_router
from app.api.dashboard import router as dashboard_router
from app.api.user import router as user_router
from app.db.models import create_db_and_tables

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: create DB tables on startup."""
    logger.info("Starting up — initialising database tables.")
    create_db_and_tables()
    yield
    logger.info("Shutting down.")


app = FastAPI(title="SDCS Ghost Ledger MVP", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(webhook_router)
app.include_router(dashboard_router)
app.include_router(user_router)


@app.get("/")
def read_root():
    return {"status": "SDCS MVP is running"}
