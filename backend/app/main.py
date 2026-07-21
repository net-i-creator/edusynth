import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.api import auth, lessons, quiz, dashboard, support

settings = get_settings()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting УмБаза API...")
    yield
    logger.info("Shutting down УмБаза API...")


app = FastAPI(
    title="УмБаза API",
    description="AI-powered educational platform for generating personalized lessons",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(auth.router)
app.include_router(support.router)
app.include_router(lessons.router)
app.include_router(quiz.router)
app.include_router(dashboard.router)


@app.get("/api/config")
async def site_config():
    return {
        "auth_enabled": settings.auth_enabled,
        "support_email": settings.support_email,
    }


@app.get("/health")
async def health_check():
    db_ok = False
    try:
        from sqlalchemy import text
        from app.db.database import async_session

        async with async_session() as session:
            await session.execute(text("SELECT 1"))
            db_ok = True
    except Exception as e:
        logger.warning("Health check DB error: %s", e)

    return {
        "status": "healthy" if db_ok else "degraded",
        "version": "1.0.0",
        "database": "ok" if db_ok else "error",
    }


FRONTEND_DIR = Path(os.environ.get("FRONTEND_DIR", ""))
if not FRONTEND_DIR.is_dir():
    FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"

if FRONTEND_DIR.is_dir():
    @app.get("/lesson")
    async def lesson_page():
        return FileResponse(FRONTEND_DIR / "lesson.html")

    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
