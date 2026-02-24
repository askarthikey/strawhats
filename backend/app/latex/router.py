from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel
from app.latex import service
from app.auth.dependencies import get_current_user
import base64

router = APIRouter(prefix="/latex", tags=["LaTeX"])


class LaTeXRequest(BaseModel):
    prompt: str
    type: str = "general"  # equation, table, algorithm, figure, general
    provider: str = "ollama"


class CompileRequest(BaseModel):
    source: str
    timeout: int = 30


@router.post("/generate")
async def generate_latex(
    req: LaTeXRequest,
    current_user: dict = Depends(get_current_user),
):
    result = await service.generate_latex(req.prompt, req.type, req.provider)
    return result


@router.post("/compile")
async def compile_latex(
    req: CompileRequest,
    current_user: dict = Depends(get_current_user),
):
    """Compile LaTeX source to PDF. Returns JSON with pdf_base64 or errors."""
    result = await service.compile_latex(req.source, req.timeout)
    return result


@router.post("/compile/pdf")
async def compile_latex_pdf(
    req: CompileRequest,
    current_user: dict = Depends(get_current_user),
):
    """Compile LaTeX source and return raw PDF bytes."""
    result = await service.compile_latex(req.source, req.timeout)
    if result["success"]:
        pdf_bytes = base64.b64decode(result["pdf_base64"])
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": "inline; filename=document.pdf"},
        )
    return result
