from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import datasets, discovery, health, research
from app.config import settings
from database.connection import close_database, open_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    open_database()
    try:
        yield
    finally:
        close_database()

app = FastAPI(
    title="Research Dataset Discovery API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1")
app.include_router(datasets.router, prefix="/api/v1")
app.include_router(datasets.analysis_router, prefix="/api/v1")
app.include_router(discovery.router, prefix="/api/v1")
app.include_router(research.router, prefix="/api/v1")
