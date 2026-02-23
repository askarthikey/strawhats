from fastapi import APIRouter
from app.admin import service

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/health")
async def health_check():
    return await service.health_check()


@router.get("/metrics")
async def get_metrics():
    return await service.get_metrics()
