from fastapi import APIRouter, Depends
from app.search.schemas import SearchRequest, HybridSearchRequest, SearchResponse
from app.search.service import semantic_search, hybrid_search
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/search", tags=["Search"])


@router.post("/semantic", response_model=SearchResponse)
async def search_semantic(
    req: SearchRequest,
    current_user: dict = Depends(get_current_user),
):
    """Semantic search using vector similarity."""
    results, search_time = await semantic_search(
        query=req.query,
        workspace_id=req.workspace_id,
        top_k=req.top_k,
        use_mmr=req.use_mmr,
        year_from=req.year_from,
        year_to=req.year_to,
    )
    return SearchResponse(
        results=results,
        query=req.query,
        total=len(results),
        search_time_ms=search_time,
    )


@router.post("/hybrid", response_model=SearchResponse)
async def search_hybrid(
    req: HybridSearchRequest,
    current_user: dict = Depends(get_current_user),
):
    """Hybrid search combining semantic + keyword search."""
    results, search_time = await hybrid_search(
        query=req.query,
        workspace_id=req.workspace_id,
        top_k=req.top_k,
        semantic_weight=req.semantic_weight,
        year_from=req.year_from,
        year_to=req.year_to,
    )
    return SearchResponse(
        results=results,
        query=req.query,
        total=len(results),
        search_time_ms=search_time,
    )
