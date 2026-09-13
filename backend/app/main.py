"""
LedgerFlow Agent — FastAPI Application Entry Point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api.routes import router
from app.db.session import engine
from app.db.session import SessionLocal
from app.models.models import Base
from app.models.models import Entity
from app.core.config import get_settings

# Create tables on startup (for development; use Alembic in production)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="LedgerFlow Agent API",
    description=(
        "Autonomous Reconciliation Agent with Explainable Cash Flow Forecasting. "
        "Track 4 — Phase 1 MVP."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

settings = get_settings()
configured_origins = {
    origin.strip()
    for origin in settings.cors_origins.split(",")
    if origin.strip()
}
configured_origins.update({
    "http://localhost:3000",
    "https://ledgerflow-riyansh.vercel.app",
})

app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(configured_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/v1")


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "ledgerflow-agent", "version": "1.0.0"}


@app.on_event("startup")
async def startup_event():
    logger.info("LedgerFlow Agent API starting up...")
    db = SessionLocal()
    try:
        if not db.query(Entity).filter_by(id="ENTITY-US-001").first():
            logger.info("Demo entity not found; running initial data seed...")
            from scripts.seed_data import seed
            seed(db)
            logger.info("Initial data seed complete.")
    finally:
        db.close()
