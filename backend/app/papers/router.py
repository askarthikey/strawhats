from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, BackgroundTasks, Query, status
from typing import List, Optional
from app.papers.schemas import (
    PaperResponse, PaperImportRequest, PaperSearchExternalRequest,
    PaperMetadata, BatchImportRequest,
)
from app.papers import service
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/papers", tags=["Papers"])


@router.post("/search-external")
async def search_external_papers(
    req: PaperSearchExternalRequest,
    current_user: dict = Depends(get_current_user),
):
    """Search external APIs (OpenAlex, Crossref, arXiv, PubMed) for papers."""
    papers = await service.search_external(req.query, req.source, req.limit)
    return {"papers": [p.model_dump() for p in papers], "count": len(papers)}


@router.post("/import")
async def import_paper(
    req: PaperImportRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """Import a paper by query/DOI into a workspace."""
    # Search for the paper
    papers = await service.search_external(
        req.query or req.doi, req.source, limit=1
    )
    if not papers:
        raise HTTPException(status_code=404, detail="Paper not found")

    result = await service.import_paper(
        papers[0], req.workspace_id, current_user["id"], background_tasks
    )
    return result


@router.post("/import-metadata")
async def import_paper_metadata(
    metadata: PaperMetadata,
    workspace_id: str = Query(...),
    background_tasks: BackgroundTasks = None,
    current_user: dict = Depends(get_current_user),
):
    """Import a paper using provided metadata."""
    result = await service.import_paper(
        metadata, workspace_id, current_user["id"], background_tasks
    )
    return result


@router.post("/upload")
async def upload_paper(
    file: UploadFile = File(...),
    workspace_id: str = Form(...),
    title: Optional[str] = Form(None),
    background_tasks: BackgroundTasks = None,
    current_user: dict = Depends(get_current_user),
):
    """Upload a PDF file to a workspace."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    result = await service.upload_paper(
        file, workspace_id, current_user["id"], title, background_tasks
    )
    return result


@router.post("/batch-import")
async def batch_import(
    req: BatchImportRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """Batch import papers by DOI list."""
    result = await service.batch_import(
        req.dois, req.workspace_id, current_user["id"], background_tasks
    )
    return result


@router.get("/", response_model=List[dict])
async def list_papers(
    workspace_id: str = Query(...),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """List papers in a workspace."""
    papers = await service.list_papers(workspace_id, skip, limit)
    return papers


@router.get("/{paper_id}")
async def get_paper(
    paper_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get a paper by ID."""
    paper = await service.get_paper(paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    return paper


@router.get("/{paper_id}/pdf-url")
async def get_paper_pdf_url(
    paper_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get signed PDF URL for a paper."""
    url = await service.get_paper_pdf_url(paper_id)
    if not url:
        raise HTTPException(status_code=404, detail="PDF not available")
    return {"url": url}


@router.delete("/{paper_id}")
async def delete_paper(
    paper_id: str,
    workspace_id: str = Query(...),
    current_user: dict = Depends(get_current_user),
):
    """Delete a paper and its chunks/vectors."""
    deleted = await service.delete_paper(paper_id, workspace_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Paper not found")
    return {"message": "Paper deleted successfully"}
