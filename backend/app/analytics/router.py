"""Analytics router: workspace-level analytics endpoint."""

from fastapi import APIRouter, Depends, HTTPException
from app.analytics import service
from app.auth.dependencies import get_current_user
from app.workspaces.service import check_permission

router = APIRouter(prefix="/workspaces", tags=["Analytics"])


@router.get("/{workspace_id}/analytics")
async def get_workspace_analytics(
    workspace_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get analytics data for a workspace."""
    # Any member can view analytics
    has_access = await check_permission(workspace_id, current_user["id"], "viewer")
    if not has_access:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    result = await service.get_workspace_analytics(workspace_id)
    if not result:
        raise HTTPException(status_code=404, detail="Workspace not found")

    return result
