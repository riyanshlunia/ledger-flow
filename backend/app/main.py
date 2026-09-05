"""
LedgerFlow Agent — FastAPI Application Entry Point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api.routes import router
from app.db.session import engine
from app.models.models import Base

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production with specific origins
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
