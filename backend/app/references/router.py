from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from typing import List
from app.references import service
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/references", tags=["References"])


class ExportRequest(BaseModel):
    paper_ids: List[str]


@router.post("/bibtex")
async def export_bibtex(
    req: ExportRequest,
    current_user: dict = Depends(get_current_user),
):
    bibtex = await service.to_bibtex(req.paper_ids)
    return PlainTextResponse(
        content=bibtex,
        media_type="application/x-bibtex",
        headers={"Content-Disposition": "attachment; filename=references.bib"},
    )


@router.post("/ris")
async def export_ris(
    req: ExportRequest,
    current_user: dict = Depends(get_current_user),
):
    ris = await service.to_ris(req.paper_ids)
    return PlainTextResponse(
        content=ris,
        media_type="application/x-research-info-systems",
        headers={"Content-Disposition": "attachment; filename=references.ris"},
    )
