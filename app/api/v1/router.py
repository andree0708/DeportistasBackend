"""Router principal de la API v1."""
from fastapi import APIRouter
from app.api.v1.endpoints import auth, runner, activities, predictions, recovery, recommendations, dashboard

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(runner.router)
api_router.include_router(activities.router)
api_router.include_router(predictions.router)
api_router.include_router(recovery.router)
api_router.include_router(recommendations.router)
api_router.include_router(dashboard.router)
