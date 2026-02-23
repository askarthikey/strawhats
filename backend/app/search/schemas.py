from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime


class SearchRequest(BaseModel):
    query: str
    workspace_id: str
    top_k: int = Field(default=10, ge=1, le=50)
    use_mmr: bool = False
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    venue: Optional[str] = None


class HybridSearchRequest(SearchRequest):
    semantic_weight: float = Field(default=0.7, ge=0.0, le=1.0)


class SearchResult(BaseModel):
    chunk_id: str
    paper_id: str
    paper_title: str
    authors: List[str] = []
    year: Optional[int] = None
    venue: Optional[str] = None
    page_number: Optional[int] = None
    snippet: str
    score: float
    doi: Optional[str] = None


class SearchResponse(BaseModel):
    results: List[SearchResult]
    query: str
    total: int
    search_time_ms: float
