from fastapi import APIRouter, Depends, HTTPException, status
from app.drafts.schemas import DraftCreate, DraftUpdate, DraftResponse, VersionResponse, DiffResponse
from app.drafts import service
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/drafts", tags=["Drafts"])


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_draft(
    req: DraftCreate,
    current_user: dict = Depends(get_current_user),
):
    return await service.create_draft(
        workspace_id=req.workspace_id,
        title=req.title,
        content=req.content_markdown,
        author_id=current_user["id"],
        author_name=current_user["full_name"],
    )


@router.get("/")
async def list_drafts(
    workspace_id: str,
    current_user: dict = Depends(get_current_user),
):
    return await service.list_drafts(workspace_id)


@router.get("/{draft_id}")
async def get_draft(
    draft_id: str,
    current_user: dict = Depends(get_current_user),
):
    draft = await service.get_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    return draft


@router.put("/{draft_id}")
async def update_draft(
    draft_id: str,
    req: DraftUpdate,
    current_user: dict = Depends(get_current_user),
):
    result = await service.update_draft(
        draft_id, req.title, req.content_markdown, req.referenced_chunk_ids
    )
    if not result:
        raise HTTPException(status_code=404, detail="Draft not found")
    return result


@router.delete("/{draft_id}")
async def delete_draft(
    draft_id: str,
    current_user: dict = Depends(get_current_user),
):
    deleted = await service.delete_draft(draft_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Draft not found")
    return {"message": "Draft deleted"}


@router.post("/{draft_id}/snapshot")
async def create_snapshot(
    draft_id: str,
    current_user: dict = Depends(get_current_user),
):
    version = await service.create_snapshot(
        draft_id, current_user["id"], current_user["full_name"]
    )
    if not version:
        raise HTTPException(status_code=404, detail="Draft not found")
    return version


@router.get("/{draft_id}/versions")
async def get_versions(
    draft_id: str,
    current_user: dict = Depends(get_current_user),
):
    return await service.get_versions(draft_id)


@router.get("/{draft_id}/versions/{version_a}/diff/{version_b}")
async def get_version_diff(
    draft_id: str,
    version_a: int,
    version_b: int,
    current_user: dict = Depends(get_current_user),
):
    result = await service.get_version_diff(draft_id, version_a, version_b)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/{draft_id}/rollback/{version_id}")
async def rollback(
    draft_id: str,
    version_id: str,
    current_user: dict = Depends(get_current_user),
):
    result = await service.rollback_to_version(draft_id, version_id)
    if not result:
        raise HTTPException(status_code=404, detail="Version not found")
    return result
