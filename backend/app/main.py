import logging

# Configure root logger before app modules import — must run first
# so app.* loggers created at import time inherit the level.
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

from contextlib import asynccontextmanager  # noqa: E402

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.api.adp import router as adp_router  # noqa: E402
from app.api.auth import router as auth_router  # noqa: E402
from app.api.health import router as health_router  # noqa: E402
from app.api.leagues import router as leagues_router  # noqa: E402
from app.api.platforms import router as platforms_router  # noqa: E402
from app.api.sync import router as sync_router  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.database import engine  # noqa: E402
from app.sync.scheduler import start_scheduler, stop_scheduler  # noqa: E402


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
