"""Workspace service: CRUD, members, invites."""

from typing import List, Optional
from bson import ObjectId
from datetime import datetime, timezone, timedelta
import secrets

from app.database import get_db
from app.utils.helpers import utc_now, serialize_doc
from app.workspaces.schemas import MemberRole


async def create_workspace(name: str, description: str, owner_id: str, owner_email: str, owner_name: str) -> dict:
    db = get_db()
    doc = {
        "name": name,
        "description": description,
        "owner_id": owner_id,
        "members": [
            {
                "user_id": owner_id,
                "email": owner_email,
                "full_name": owner_name,
                "role": MemberRole.OWNER,
            }
        ],
        "paper_count": 0,
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    result = await db.workspaces.insert_one(doc)
    doc["_id"] = result.inserted_id
    return serialize_doc(doc)


async def get_workspace(workspace_id: str) -> Optional[dict]:
    db = get_db()
    try:
        doc = await db.workspaces.find_one({"_id": ObjectId(workspace_id)})
        return serialize_doc(doc) if doc else None
    except Exception:
        return None


async def list_workspaces(user_id: str) -> List[dict]:
    db = get_db()
    cursor = db.workspaces.find(
        {"members.user_id": user_id}
    ).sort("updated_at", -1)

    workspaces = []
    async for doc in cursor:
        # Get paper count
        paper_count = await db.papers.count_documents({"workspace_id": str(doc["_id"])})
        doc["paper_count"] = paper_count
        workspaces.append(serialize_doc(doc))

    return workspaces


async def update_workspace(workspace_id: str, name: str = None, description: str = None) -> Optional[dict]:
    db = get_db()
    update = {"$set": {"updated_at": utc_now()}}
    if name is not None:
        update["$set"]["name"] = name
    if description is not None:
        update["$set"]["description"] = description

    result = await db.workspaces.find_one_and_update(
        {"_id": ObjectId(workspace_id)},
        update,
        return_document=True,
    )
    return serialize_doc(result) if result else None


async def delete_workspace(workspace_id: str) -> bool:
    db = get_db()
    # Delete all papers, chunks, chat logs, drafts in workspace
    await db.papers.delete_many({"workspace_id": workspace_id})
    await db.chunks.delete_many({"workspace_id": workspace_id})
    await db.chat_logs.delete_many({"workspace_id": workspace_id})
    await db.drafts.delete_many({"workspace_id": workspace_id})
    await db.draft_versions.delete_many({"workspace_id": workspace_id})

    result = await db.workspaces.delete_one({"_id": ObjectId(workspace_id)})
    return result.deleted_count > 0


async def add_member(workspace_id: str, email: str, role: MemberRole) -> Optional[dict]:
    db = get_db()
    user = await db.users.find_one({"email": email})
    if not user:
        return None

    member = {
        "user_id": str(user["_id"]),
        "email": email,
        "full_name": user.get("full_name", ""),
        "role": role,
    }

    # Check if already a member
    workspace = await db.workspaces.find_one({
        "_id": ObjectId(workspace_id),
        "members.user_id": str(user["_id"]),
    })
    if workspace:
        # Update role
        await db.workspaces.update_one(
            {"_id": ObjectId(workspace_id), "members.user_id": str(user["_id"])},
            {"$set": {"members.$.role": role}},
        )
    else:
        await db.workspaces.update_one(
            {"_id": ObjectId(workspace_id)},
            {"$push": {"members": member}},
        )

    return member


async def remove_member(workspace_id: str, user_id: str) -> bool:
    db = get_db()
    result = await db.workspaces.update_one(
        {"_id": ObjectId(workspace_id)},
        {"$pull": {"members": {"user_id": user_id}}},
    )
    return result.modified_count > 0


async def get_members(workspace_id: str) -> List[dict]:
    db = get_db()
    workspace = await db.workspaces.find_one({"_id": ObjectId(workspace_id)})
    if not workspace:
        return []
    return workspace.get("members", [])


async def create_invite_link(workspace_id: str, role: MemberRole, expires_hours: int = 72) -> str:
    db = get_db()
    token = secrets.token_urlsafe(32)
    invite = {
        "workspace_id": workspace_id,
        "token": token,
        "role": role,
        "expires_at": utc_now() + timedelta(hours=expires_hours),
        "created_at": utc_now(),
        "used": False,
    }
    await db.workspace_invites.insert_one(invite)
    return token


async def join_via_invite(token: str, user_id: str, email: str, full_name: str) -> Optional[dict]:
    db = get_db()
    invite = await db.workspace_invites.find_one({
        "token": token,
        "used": False,
        "expires_at": {"$gt": utc_now()},
    })
    if not invite:
        return None

    workspace_id = invite["workspace_id"]
    role = invite.get("role", MemberRole.VIEWER)

    await add_member(workspace_id, email, role)

    # Mark invite as used
    await db.workspace_invites.update_one(
        {"_id": invite["_id"]},
        {"$set": {"used": True}},
    )

    return await get_workspace(workspace_id)


async def check_permission(workspace_id: str, user_id: str, required_role: MemberRole = MemberRole.VIEWER) -> bool:
    """Check if user has at least the required role in workspace."""
    db = get_db()
    role_hierarchy = {
        MemberRole.OWNER: 4,
        MemberRole.EDITOR: 3,
        MemberRole.COMMENTER: 2,
        MemberRole.VIEWER: 1,
    }

    workspace = await db.workspaces.find_one({
        "_id": ObjectId(workspace_id),
        "members.user_id": user_id,
    })
    if not workspace:
        return False

    for member in workspace.get("members", []):
        if member["user_id"] == user_id:
            user_level = role_hierarchy.get(member["role"], 0)
            required_level = role_hierarchy.get(required_role, 0)
            return user_level >= required_level

    return False
