from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class DraftCreate(BaseModel):
    workspace_id: str
    title: str = Field(..., min_length=1, max_length=200)
    content_markdown: str = ""


class DraftUpdate(BaseModel):
    title: Optional[str] = None
    content_markdown: Optional[str] = None
    referenced_chunk_ids: Optional[List[str]] = None


class DraftResponse(BaseModel):
    id: str
    workspace_id: str
    title: str
    content_markdown: str
    author_id: str
    author_name: str
    version: int
    referenced_chunk_ids: List[str] = []
    created_at: datetime
    updated_at: datetime


class VersionResponse(BaseModel):
    id: str
    draft_id: str
    version: int
    author_id: str
    author_name: str
    title: str
    content_markdown: str
    diff_summary: str = ""
    created_at: datetime


class DiffResponse(BaseModel):
    version_a: int
    version_b: int
    diffs: list
    html_diff: str = ""
