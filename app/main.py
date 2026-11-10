"""Punto de entrada de la aplicación FastAPI - RunSense AI Backend."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.api.v1.router import api_router

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address, default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 RunSense AI Backend arrancando...")
    yield
    logger.info("🛑 RunSense AI Backend apagándose...")
    from app.grpc_client.ai_client import ai_client
    ai_client.close()


app = FastAPI(
    title="RunSense AI — Backend",
    description="API REST para la plataforma de análisis de rendimiento deportivo en corredores",
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Error no controlado: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Error interno del servidor"},
    )


# Rutas
app.include_router(api_router)


@app.get("/health", tags=["Sistema"])
def health():
    return {"status": "ok", "service": "RunSense AI Backend", "version": settings.APP_VERSION}


@app.get("/", tags=["Sistema"])
def root():
    return {"message": "RunSense AI Backend", "docs": "/docs"}
