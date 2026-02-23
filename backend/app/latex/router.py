from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.latex import service
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/latex", tags=["LaTeX"])


class LaTeXRequest(BaseModel):
    prompt: str
    type: str = "general"  # equation, table, algorithm, figure, general
    provider: str = "ollama"


@router.post("/generate")
async def generate_latex(
    req: LaTeXRequest,
    current_user: dict = Depends(get_current_user),
):
    result = await service.generate_latex(req.prompt, req.type, req.provider)
    return result
