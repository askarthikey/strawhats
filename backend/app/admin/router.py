from fastapi import APIRouter, Depends, HTTPException, status
from app.admin import service
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/admin", tags=["Admin"])


async def require_admin(current_user: dict = Depends(get_current_user)):
    if current_user.get("role", "user") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


@router.get("/health")
async def health_check(current_user: dict = Depends(require_admin)):
    return await service.health_check()


@router.get("/metrics")
async def get_metrics(current_user: dict = Depends(require_admin)):
    return await service.get_metrics()
