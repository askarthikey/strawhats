from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class PaperStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


class PaperMetadata(BaseModel):
    title: str
    authors: List[str] = []
    doi: Optional[str] = None
    year: Optional[int] = None
    venue: Optional[str] = None
    abstract: Optional[str] = None
    pdf_url: Optional[str] = None
    license: Optional[str] = None
    source: Optional[str] = None  # openalex, crossref, arxiv, pubmed, upload


class PaperCreate(BaseModel):
    title: str
    authors: List[str] = []
    doi: Optional[str] = None
    year: Optional[int] = None
    venue: Optional[str] = None
    abstract: Optional[str] = None
    workspace_id: str


class PaperResponse(BaseModel):
    id: str
    title: str
    authors: List[str] = []
    doi: Optional[str] = None
    year: Optional[int] = None
    venue: Optional[str] = None
    abstract: Optional[str] = None
    pdf_url: Optional[str] = None
    storage_path: Optional[str] = None
    status: PaperStatus = PaperStatus.PENDING
    chunk_count: int = 0
    workspace_id: str
    created_at: datetime
    source: Optional[str] = None


class PaperImportRequest(BaseModel):
    query: Optional[str] = None
    doi: Optional[str] = None
    workspace_id: str
    source: str = "openalex"  # openalex, crossref, arxiv, pubmed


class PaperSearchExternalRequest(BaseModel):
    query: str
    source: str = "openalex"
    limit: int = Field(default=10, ge=1, le=50)


class BatchImportRequest(BaseModel):
    dois: List[str]
    workspace_id: str


class ChunkData(BaseModel):
    chunk_index: int
    text: str
    page_number: Optional[int] = None
    char_start: int
    char_end: int
    checksum: str
    token_count: int


class ChunkResponse(BaseModel):
    id: str
    paper_id: str
    chunk_index: int
    text: str
    page_number: Optional[int] = None
    char_start: int
    char_end: int
    token_count: int
