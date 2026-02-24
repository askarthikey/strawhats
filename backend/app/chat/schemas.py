from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime


class ChatMessage(BaseModel):
    role: str = "user"  # user, assistant
    content: str


class ChatRequest(BaseModel):
    question: str
    workspace_id: str
    paper_ids: Optional[List[str]] = None  # Filter to specific papers
    template: str = "default"  # default, summarize, compare, extract_methods, generate_review
    provider: str = "gemini"  # gemini, ollama
    top_k: int = Field(default=10, ge=1, le=50)
    temperature: float = Field(default=0.0, ge=0.0, le=1.0)
    use_mmr: bool = False
    chat_history: List[ChatMessage] = []


class CitationInfo(BaseModel):
    chunk_id: str
    paper_id: Optional[str] = None
    title: str = "Unknown"
    authors: List[str] = []
    page: Optional[int] = None
    snippet: str = ""
    year: Optional[int] = None
    doi: Optional[str] = None


class ChatStreamEvent(BaseModel):
    type: str = "token"  # token, citation, done, error
    token: Optional[str] = None
    citations: Optional[List[CitationInfo]] = None
    full_response: Optional[str] = None
    metadata: Optional[Dict] = None
    error: Optional[str] = None


class ChatLogResponse(BaseModel):
    id: str
    workspace_id: str
    user_id: str
    question: str
    answer: str
    citations: List[CitationInfo] = []
    template: str = "default"
    provider: str = "ollama"
    created_at: datetime
