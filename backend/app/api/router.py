from fastapi import APIRouter

from app.api.routes.covers import admin_router, router as covers_router
from app.api.routes.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(covers_router, tags=["covers"])
api_router.include_router(admin_router, tags=["admin"])
