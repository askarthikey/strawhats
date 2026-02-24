"""AI writing assistant for drafts: suggestions, improvements, citations."""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from app.auth.dependencies import get_current_user
from app.llm.provider import get_llm_provider

router = APIRouter(prefix="/drafts/ai", tags=["Draft AI"])


class SuggestRequest(BaseModel):
    context: str
    workspace_id: str
    instruction: Optional[str] = None


class ImproveRequest(BaseModel):
    text: str
    instruction: Optional[str] = None


class CiteRequest(BaseModel):
    text: str
    workspace_id: str


@router.post("/suggest")
async def suggest_completion(
    req: SuggestRequest,
    current_user: dict = Depends(get_current_user),
):
    """Generate AI-powered text suggestion based on current context."""
    provider = await get_llm_provider("ollama")

    instruction = req.instruction or "Continue writing this research paper section"

    system_prompt = (
        "You are an expert academic writing assistant helping write a research paper. "
        "Continue the text naturally, maintaining the same style, tone, and formatting. "
        "Use academic language appropriate for a peer-reviewed paper. "
        "Keep your continuation concise (2-4 sentences). "
        "If the text contains LaTeX or Markdown formatting, continue with the same formatting."
    )

    prompt = f"""Here is the current text from a research paper draft:

---
{req.context}
---

Instruction: {instruction}

Continue writing from where the text ends. Provide 2-4 sentences that naturally follow:"""

    try:
        result = await provider.generate(prompt, system_prompt=system_prompt)
        return {"suggestion": result.strip()}
    except Exception as e:
        return {"suggestion": "", "error": str(e)}


@router.post("/improve")
async def improve_text(
    req: ImproveRequest,
    current_user: dict = Depends(get_current_user),
):
    """Improve or rewrite selected text."""
    provider = await get_llm_provider("ollama")

    instruction = req.instruction or "Improve the clarity, grammar, and academic tone"

    system_prompt = (
        "You are an expert academic editor. Improve the given text while preserving "
        "its meaning and any LaTeX/Markdown formatting. Return ONLY the improved text, "
        "no explanations."
    )

    prompt = f"""Improve the following text:

---
{req.text}
---

Instruction: {instruction}

Improved version:"""

    try:
        result = await provider.generate(prompt, system_prompt=system_prompt)
        return {"improved": result.strip()}
    except Exception as e:
        return {"improved": req.text, "error": str(e)}


@router.post("/cite")
async def find_citations(
    req: CiteRequest,
    current_user: dict = Depends(get_current_user),
):
    """Find relevant citations for a piece of text from the workspace papers."""
    from app.search.service import semantic_search

    try:
        results, _ = await semantic_search(
            query=req.text,
            workspace_id=req.workspace_id,
            top_k=5,
        )

        citations = []
        for r in results:
            citations.append({
                "paper_title": r.paper_title,
                "authors": r.authors,
                "year": r.year,
                "snippet": r.snippet,
                "doi": r.doi,
                "score": r.score,
            })

        return {"citations": citations}
    except Exception as e:
        return {"citations": [], "error": str(e)}


class InlineSuggestRequest(BaseModel):
    context_before: str  # text before cursor (last ~500 chars)
    context_after: str = ""  # text after cursor
    full_title: str = ""


@router.post("/inline-suggest")
async def inline_suggest(
    req: InlineSuggestRequest,
    current_user: dict = Depends(get_current_user),
):
    """Stream an inline completion (ghost text) for the cursor position."""
    provider = await get_llm_provider("ollama")

    system_prompt = (
        "You are an inline autocomplete engine for academic research papers. "
        "Complete the text from exactly where it ends. "
        "Output ONLY the completion text — no quotes, no explanations, no prefixes. "
        "Keep it to 1-2 short sentences max. "
        "Match the style, formatting (Markdown/LaTeX), and language of the existing text. "
        "If the text ends mid-sentence, finish that sentence first."
    )

    title_hint = f"Paper title: {req.full_title}\n" if req.full_title else ""
    after_hint = f"\n\n[Text after cursor]: {req.context_after[:200]}" if req.context_after.strip() else ""

    prompt = f"""{title_hint}[Text before cursor]:
{req.context_before}{after_hint}

Continue writing from exactly where the text before cursor ends:"""

    async def stream():
        try:
            async for token in provider.generate_stream(
                prompt, system_prompt=system_prompt, temperature=0.3, max_tokens=150
            ):
                yield token
        except Exception:
            yield ""

    return StreamingResponse(stream(), media_type="text/plain")
