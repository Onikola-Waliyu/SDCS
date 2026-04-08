import logging
from contextlib import asynccontextmanager

import os
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import text

from app.api.webhook import router as webhook_router
from app.api.dashboard import router as dashboard_router
from app.api.user import router as user_router
from app.db.models import create_db_and_tables, engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: create DB tables on startup."""
    logger.info("Starting up — initialising database tables.")
    create_db_and_tables()
    # Safely inject the new status column for existing legacy DB instances without dropping data
    try:
        with engine.connect() as conn:
            conn.execute(text('ALTER TABLE "transaction" ADD COLUMN IF NOT EXISTS status VARCHAR DEFAULT \'recorded\';'))
            conn.commit()
            logger.info("Successfully migrated status column.")
    except Exception as e:
        logger.info(f"Migration suppressed: {e}")
    yield
    logger.info("Shutting down.")


app = FastAPI(title="SDCS Ledger MVP", lifespan=lifespan)

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

app.include_router(webhook_router)
app.include_router(dashboard_router)
app.include_router(user_router)


@app.get("/")
def read_root(request: Request):
    bot_phone = os.getenv("WHATSAPP_PHONE_NUMBER", "234...")
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"bot_phone": bot_phone}
    )
