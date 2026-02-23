"""Draft service: CRUD, versioning, diff, rollback."""

from typing import List, Optional
from bson import ObjectId
from diff_match_patch import diff_match_patch

from app.database import get_db
from app.utils.helpers import utc_now, serialize_doc

dmp = diff_match_patch()


async def create_draft(workspace_id: str, title: str, content: str, author_id: str, author_name: str) -> dict:
    db = get_db()
    doc = {
        "workspace_id": workspace_id,
        "title": title,
        "content_markdown": content,
        "author_id": author_id,
        "author_name": author_name,
        "version": 1,
        "referenced_chunk_ids": [],
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    result = await db.drafts.insert_one(doc)
    doc["_id"] = result.inserted_id
    return serialize_doc(doc)


async def get_draft(draft_id: str) -> Optional[dict]:
    db = get_db()
    try:
        doc = await db.drafts.find_one({"_id": ObjectId(draft_id)})
        return serialize_doc(doc) if doc else None
    except Exception:
        return None


async def list_drafts(workspace_id: str) -> List[dict]:
    db = get_db()
    cursor = db.drafts.find({"workspace_id": workspace_id}).sort("updated_at", -1)
    drafts = []
    async for doc in cursor:
        drafts.append(serialize_doc(doc))
    return drafts


async def update_draft(draft_id: str, title: str = None, content: str = None, chunk_ids: list = None) -> Optional[dict]:
    db = get_db()
    update = {"$set": {"updated_at": utc_now()}}
    if title is not None:
        update["$set"]["title"] = title
    if content is not None:
        update["$set"]["content_markdown"] = content
    if chunk_ids is not None:
        update["$set"]["referenced_chunk_ids"] = chunk_ids

    result = await db.drafts.find_one_and_update(
        {"_id": ObjectId(draft_id)},
        update,
        return_document=True,
    )
    return serialize_doc(result) if result else None


async def delete_draft(draft_id: str) -> bool:
    db = get_db()
    # Delete versions too
    await db.draft_versions.delete_many({"draft_id": draft_id})
    result = await db.drafts.delete_one({"_id": ObjectId(draft_id)})
    return result.deleted_count > 0


async def create_snapshot(draft_id: str, author_id: str, author_name: str) -> Optional[dict]:
    """Create a version snapshot of the current draft state."""
    db = get_db()
    draft = await db.drafts.find_one({"_id": ObjectId(draft_id)})
    if not draft:
        return None

    # Get previous version for diff
    prev_version = await db.draft_versions.find_one(
        {"draft_id": draft_id},
        sort=[("version", -1)],
    )

    new_version = (prev_version["version"] + 1) if prev_version else 1

    # Calculate diff summary
    diff_summary = ""
    if prev_version:
        diffs_result = dmp.diff_main(
            prev_version.get("content_markdown", ""),
            draft.get("content_markdown", ""),
        )
        dmp.diff_cleanupSemantic(diffs_result)
        added = sum(len(text) for op, text in diffs_result if op == 1)
        removed = sum(len(text) for op, text in diffs_result if op == -1)
        diff_summary = f"+{added} chars, -{removed} chars"

    version_doc = {
        "draft_id": draft_id,
        "version": new_version,
        "author_id": author_id,
        "author_name": author_name,
        "title": draft.get("title", ""),
        "content_markdown": draft.get("content_markdown", ""),
        "diff_summary": diff_summary,
        "workspace_id": draft.get("workspace_id", ""),
        "created_at": utc_now(),
    }
    result = await db.draft_versions.insert_one(version_doc)
    version_doc["_id"] = result.inserted_id

    # Update draft version number
    await db.drafts.update_one(
        {"_id": ObjectId(draft_id)},
        {"$set": {"version": new_version, "updated_at": utc_now()}},
    )

    return serialize_doc(version_doc)


async def get_versions(draft_id: str) -> List[dict]:
    db = get_db()
    cursor = db.draft_versions.find({"draft_id": draft_id}).sort("version", -1)
    versions = []
    async for doc in cursor:
        versions.append(serialize_doc(doc))
    return versions


async def get_version_diff(draft_id: str, version_a: int, version_b: int) -> dict:
    """Compute diff between two versions."""
    db = get_db()
    va = await db.draft_versions.find_one({"draft_id": draft_id, "version": version_a})
    vb = await db.draft_versions.find_one({"draft_id": draft_id, "version": version_b})

    if not va or not vb:
        return {"error": "Version not found"}

    text_a = va.get("content_markdown", "")
    text_b = vb.get("content_markdown", "")

    diffs_result = dmp.diff_main(text_a, text_b)
    dmp.diff_cleanupSemantic(diffs_result)
    html_diff = dmp.diff_prettyHtml(diffs_result)

    return {
        "version_a": version_a,
        "version_b": version_b,
        "diffs": diffs_result,
        "html_diff": html_diff,
    }


async def rollback_to_version(draft_id: str, version_id: str) -> Optional[dict]:
    """Rollback a draft to a specific version."""
    db = get_db()
    version = await db.draft_versions.find_one({"_id": ObjectId(version_id), "draft_id": draft_id})
    if not version:
        return None

    result = await db.drafts.find_one_and_update(
        {"_id": ObjectId(draft_id)},
        {
            "$set": {
                "title": version.get("title", ""),
                "content_markdown": version.get("content_markdown", ""),
                "updated_at": utc_now(),
            }
        },
        return_document=True,
    )
    return serialize_doc(result) if result else None
