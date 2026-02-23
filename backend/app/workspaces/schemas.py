from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class MemberRole(str, Enum):
    OWNER = "owner"
    EDITOR = "editor"
    COMMENTER = "commenter"
    VIEWER = "viewer"


class WorkspaceMember(BaseModel):
    user_id: str
    email: str
    full_name: str
    role: MemberRole


class WorkspaceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None


class WorkspaceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    owner_id: str
    members: List[WorkspaceMember] = []
    paper_count: int = 0
    created_at: datetime
    updated_at: datetime


class InviteRequest(BaseModel):
    email: str
    role: MemberRole = MemberRole.VIEWER


class InviteLinkRequest(BaseModel):
    role: MemberRole = MemberRole.VIEWER
    expires_hours: int = Field(default=72, ge=1, le=720)
