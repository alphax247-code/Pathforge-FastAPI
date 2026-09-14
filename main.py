"""Pathforge FastAPI entry point.

The existing Flask application is mounted as a compatibility layer so the
current UI and routes continue to work while they are migrated to native
FastAPI routers.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.wsgi import WSGIMiddleware

from routes.auth_routes import router as auth_router

logger = logging.getLogger(__name__)
legacy_error: str | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Pathforge FastAPI starting")
    yield
    logger.info("Pathforge FastAPI stopping")


app = FastAPI(
    title="Pathforge API",
    description="FastAPI migration of the Pathforge personal-development platform.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Native FastAPI routes must be registered before the catch-all Flask mount.
app.include_router(auth_router)


@app.get("/api/v1/health", tags=["system"])
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "pathforge-fastapi",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/v1/ready", tags=["system"])
async def readiness():
    if legacy_error:
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "legacy_app": "unavailable", "detail": legacy_error},
        )
    return {"status": "ready", "legacy_app": "mounted"}


try:
    from legacy_app import app as flask_app
except Exception as exc:  # lets health/docs expose configuration failures
    legacy_error = f"{type(exc).__name__}: {exc}"
    logger.exception("The legacy Pathforge application could not be loaded")

    @app.get("/", include_in_schema=False)
    async def configuration_error():
        return JSONResponse(
            status_code=503,
            content={
                "error": "Pathforge is not fully configured",
                "detail": legacy_error,
                "next_step": "Configure the environment variables in .env.example",
            },
        )
else:
    app.mount("/", WSGIMiddleware(flask_app), name="legacy")
