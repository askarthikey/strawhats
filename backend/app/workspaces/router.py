from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from app.workspaces.schemas import (
    WorkspaceCreate, WorkspaceUpdate, WorkspaceResponse,
    InviteRequest, InviteLinkRequest,
)
from app.workspaces import service
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_workspace(
    req: WorkspaceCreate,
    current_user: dict = Depends(get_current_user),
):
    result = await service.create_workspace(
        name=req.name,
        description=req.description,
        owner_id=current_user["id"],
        owner_email=current_user["email"],
        owner_name=current_user["full_name"],
    )
    return result


@router.get("/")
async def list_workspaces(current_user: dict = Depends(get_current_user)):
    return await service.list_workspaces(current_user["id"])


@router.get("/{workspace_id}")
async def get_workspace(
    workspace_id: str,
    current_user: dict = Depends(get_current_user),
):
    workspace = await service.get_workspace(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace


@router.put("/{workspace_id}")
async def update_workspace(
    workspace_id: str,
    req: WorkspaceUpdate,
    current_user: dict = Depends(get_current_user),
):
    if not await service.check_permission(workspace_id, current_user["id"], "editor"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    result = await service.update_workspace(workspace_id, req.name, req.description)
    if not result:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return result


@router.delete("/{workspace_id}")
async def delete_workspace(
    workspace_id: str,
    current_user: dict = Depends(get_current_user),
):
    if not await service.check_permission(workspace_id, current_user["id"], "owner"):
        raise HTTPException(status_code=403, detail="Only owners can delete workspaces")

    deleted = await service.delete_workspace(workspace_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return {"message": "Workspace deleted"}


@router.post("/{workspace_id}/invite")
async def invite_member(
    workspace_id: str,
    req: InviteRequest,
    current_user: dict = Depends(get_current_user),
):
    if not await service.check_permission(workspace_id, current_user["id"], "editor"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    member = await service.add_member(workspace_id, req.email, req.role)
    if not member:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "Member added", "member": member}


@router.post("/{workspace_id}/invite-link")
async def create_invite_link(
    workspace_id: str,
    req: InviteLinkRequest,
    current_user: dict = Depends(get_current_user),
):
    if not await service.check_permission(workspace_id, current_user["id"], "editor"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    token = await service.create_invite_link(workspace_id, req.role, req.expires_hours)
    return {"invite_token": token, "expires_hours": req.expires_hours}


@router.post("/join/{invite_token}")
async def join_workspace(
    invite_token: str,
    current_user: dict = Depends(get_current_user),
):
    result = await service.join_via_invite(
        invite_token, current_user["id"],
        current_user["email"], current_user["full_name"],
    )
    if not result:
        raise HTTPException(status_code=404, detail="Invalid or expired invite")
    return result


@router.get("/{workspace_id}/members")
async def get_members(
    workspace_id: str,
    current_user: dict = Depends(get_current_user),
):
    members = await service.get_members(workspace_id)
    return {"members": members}


@router.delete("/{workspace_id}/members/{user_id}")
async def remove_member(
    workspace_id: str,
    user_id: str,
    current_user: dict = Depends(get_current_user),
):
    # Owner or admin can remove members
    caller_role = await service.get_member_role(workspace_id, current_user["id"])
    if caller_role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only owners and admins can remove members")

    # Admin cannot remove owner
    target_role = await service.get_member_role(workspace_id, user_id)
    if target_role == "owner":
        raise HTTPException(status_code=403, detail="Cannot remove the workspace owner")

    removed = await service.remove_member(workspace_id, user_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Member not found")
    return {"message": "Member removed"}


@router.patch("/{workspace_id}/members/{user_id}/role")
async def update_member_role(
    workspace_id: str,
    user_id: str,
    body: dict,
    current_user: dict = Depends(get_current_user),
):
    """Update a member's role. Owner or Admin can change roles."""
    new_role = body.get("role", "")
    if new_role not in ("viewer", "editor", "admin"):
        raise HTTPException(status_code=400, detail="Role must be viewer, editor, or admin")

    caller_role = await service.get_member_role(workspace_id, current_user["id"])
    if caller_role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only owners and admins can change roles")

    # Admin cannot change owner's role or assign admin role (only owner can)
    target_role = await service.get_member_role(workspace_id, user_id)
    if target_role == "owner":
        raise HTTPException(status_code=403, detail="Cannot change the owner's role")

    if caller_role == "admin":
        if new_role == "admin":
            raise HTTPException(status_code=403, detail="Only owners can assign admin role")
        if target_role == "admin":
            raise HTTPException(status_code=403, detail="Only owners can change an admin's role")

    updated = await service.update_member_role(workspace_id, user_id, new_role)
    if not updated:
        raise HTTPException(status_code=404, detail="Member not found or role unchanged")
    return {"message": "Role updated"}
