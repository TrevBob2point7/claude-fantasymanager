from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.adp import router as adp_router
from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.leagues import router as leagues_router
from app.api.platforms import router as platforms_router
from app.api.sync import router as sync_router
from app.core.config import settings
from app.core.database import engine
from app.sync.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Verify DB connection on startup
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    start_scheduler()
    yield
    # Shutdown scheduler and dispose engine
    stop_scheduler()
    await engine.dispose()


app = FastAPI(title="Fantasy Manager API", lifespan=lifespan)

# TODO: Restrict allow_methods and allow_headers for production deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(platforms_router)
app.include_router(leagues_router)
app.include_router(sync_router)
app.include_router(adp_router)
