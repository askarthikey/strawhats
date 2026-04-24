"""Workspace analytics service: aggregates contributions, papers, drafts, activity."""

import re
from typing import List, Dict, Optional
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from bson import ObjectId

from app.database import get_db
from app.utils.helpers import serialize_doc


def _parse_chars_added(diff_summary: str) -> int:
    """Parse '+N chars' from a diff_summary like '+342 chars, -50 chars'."""
    if not diff_summary:
        return 0
    match = re.search(r"\+(\d+)\s*chars", diff_summary)
    return int(match.group(1)) if match else 0


async def _compute_draft_contributions(workspace_id: str) -> Dict:
    """
    Compute per-user contribution percentages for every draft in the workspace.

    For each draft:
      - Version 1 (no diff_summary) → attribute full content length to its author
      - Subsequent versions → use chars-added from diff_summary
      - Each user's contribution% = (user_chars / total_chars) * 100

    Returns:
      {
        "per_draft": {
            draft_id: {
                "title": "...",
                "total_chars": 1234,
                "contributors": {user_id: {"chars": N, "pct": X, "name": "...", "email": "..."}}
            }
        },
        "per_user": {
            user_id: {
                "name": "...",
                "email": "...",
                "draft_contributions": float,  # sum of pct/100 across drafts (draft equivalents)
                "draft_details": [{"draft_id": ..., "draft_title": ..., "contribution_pct": ...}]
            }
        }
      }
    """
    db = get_db()

    # Get all drafts in the workspace
    drafts = {}
    async for doc in db.drafts.find({"workspace_id": workspace_id}):
        draft_id = str(doc["_id"])
        drafts[draft_id] = {
            "title": doc.get("title", "Untitled"),
            "author_id": doc.get("author_id", ""),
            "author_name": doc.get("author_name", ""),
            "content_length": len(doc.get("content_markdown", "")),
        }

    per_draft = {}
    per_user = defaultdict(lambda: {
        "name": "",
        "email": "",
        "draft_contributions": 0.0,
        "draft_details": [],
    })

    for draft_id, draft_info in drafts.items():
        # Fetch all versions for this draft, ordered by version
        versions = []
        async for ver in db.draft_versions.find({"draft_id": draft_id}).sort("version", 1):
            versions.append(ver)

        # Track chars contributed per user for this draft
        user_chars: Dict[str, int] = defaultdict(int)
        user_names: Dict[str, str] = {}
        user_emails: Dict[str, str] = {}

        if not versions:
            # No snapshots yet — attribute full content to the draft author
            author_id = draft_info["author_id"]
            if author_id:
                user_chars[author_id] = max(draft_info["content_length"], 1)
                user_names[author_id] = draft_info["author_name"]
        else:
            for idx, ver in enumerate(versions):
                author_id = ver.get("author_id", "")
                if not author_id:
                    continue
                user_names[author_id] = ver.get("author_name", "")

                if idx == 0:
                    # First recorded version — attribute full content length
                    content_len = len(ver.get("content_markdown", ""))
                    user_chars[author_id] += max(content_len, 1)
                else:
                    # Subsequent versions — use diff_summary
                    chars_added = _parse_chars_added(ver.get("diff_summary", ""))
                    # Give at least 1 char credit so the contributor isn't invisible
                    user_chars[author_id] += max(chars_added, 1)

        # Calculate percentages
        total_chars = sum(user_chars.values())
        contributors = {}
        for uid, chars in user_chars.items():
            pct = (chars / total_chars * 100) if total_chars > 0 else 0
            contributors[uid] = {
                "chars": chars,
                "pct": round(pct, 1),
                "name": user_names.get(uid, ""),
                "email": user_emails.get(uid, ""),
            }

            # Accumulate into per_user
            per_user[uid]["name"] = user_names.get(uid, "")
            per_user[uid]["draft_contributions"] += pct / 100
            per_user[uid]["draft_details"].append({
                "draft_id": draft_id,
                "draft_title": draft_info["title"],
                "contribution_pct": round(pct, 1),
            })

        per_draft[draft_id] = {
            "title": draft_info["title"],
            "total_chars": total_chars,
            "contributors": contributors,
        }

    return {"per_draft": per_draft, "per_user": dict(per_user)}


async def get_workspace_analytics(workspace_id: str) -> Optional[dict]:
    """Build the full analytics payload for a workspace."""
    db = get_db()

    # --- Workspace info ---
    try:
        workspace = await db.workspaces.find_one({"_id": ObjectId(workspace_id)})
    except Exception:
        return None
    if not workspace:
        return None

    members = workspace.get("members", [])
    member_map = {m["user_id"]: m for m in members}

    # --- Summary counts ---
    total_papers = await db.papers.count_documents({"workspace_id": workspace_id})
    indexed_papers = await db.papers.count_documents({"workspace_id": workspace_id, "status": "indexed"})
    pending_papers = await db.papers.count_documents({"workspace_id": workspace_id, "status": "pending"})
    processing_papers = await db.papers.count_documents({"workspace_id": workspace_id, "status": "processing"})
    failed_papers = await db.papers.count_documents({"workspace_id": workspace_id, "status": "failed"})
    total_drafts = await db.drafts.count_documents({"workspace_id": workspace_id})
    total_draft_versions = await db.draft_versions.count_documents({"workspace_id": workspace_id})
    total_chat_sessions = await db.chat_logs.count_documents({"workspace_id": workspace_id})

    # --- Papers by source ---
    pipeline_source = [
        {"$match": {"workspace_id": workspace_id}},
        {"$group": {"_id": "$source", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    papers_by_source = []
    async for doc in db.papers.aggregate(pipeline_source):
        papers_by_source.append({"source": doc["_id"] or "unknown", "count": doc["count"]})

    # --- Papers per user (added_by) ---
    pipeline_papers_user = [
        {"$match": {"workspace_id": workspace_id}},
        {"$group": {"_id": "$added_by", "count": {"$sum": 1}}},
    ]
    papers_per_user = {}
    async for doc in db.papers.aggregate(pipeline_papers_user):
        if doc["_id"]:
            papers_per_user[doc["_id"]] = doc["count"]

    # --- Draft contributions (edit-based) ---
    draft_data = await _compute_draft_contributions(workspace_id)

    # --- Build contributors list ---
    contributors = []
    all_user_ids = set(member_map.keys()) | set(papers_per_user.keys()) | set(draft_data["per_user"].keys())

    for uid in all_user_ids:
        member_info = member_map.get(uid, {})
        draft_user = draft_data["per_user"].get(uid, {})

        papers_added = papers_per_user.get(uid, 0)
        draft_contributions = round(draft_user.get("draft_contributions", 0), 2)
        draft_details = draft_user.get("draft_details", [])
        total_score = round(papers_added + draft_contributions, 2)

        name = (
            member_info.get("full_name")
            or draft_user.get("name")
            or member_info.get("email", "Unknown")
        )

        contributors.append({
            "user_id": uid,
            "name": name,
            "email": member_info.get("email", draft_user.get("email", "")),
            "role": member_info.get("role", "—"),
            "papers_added": papers_added,
            "draft_contributions": draft_contributions,
            "draft_details": draft_details,
            "total_score": total_score,
        })

    role_rank = {"owner": 5, "admin": 4, "editor": 3, "commenter": 2, "viewer": 1}
    contributors.sort(key=lambda c: (c["total_score"], role_rank.get(c["role"], 0)), reverse=True)

    # --- Activity timeline (last 12 months) ---
    now = datetime.now(timezone.utc)
    twelve_months_ago = now - timedelta(days=365)

    pipeline_papers_timeline = [
        {"$match": {"workspace_id": workspace_id, "created_at": {"$gte": twelve_months_ago}}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m", "date": "$created_at"}},
            "count": {"$sum": 1},
        }},
        {"$sort": {"_id": 1}},
    ]
    papers_monthly = {}
    async for doc in db.papers.aggregate(pipeline_papers_timeline):
        papers_monthly[doc["_id"]] = doc["count"]

    pipeline_drafts_timeline = [
        {"$match": {"workspace_id": workspace_id, "created_at": {"$gte": twelve_months_ago}}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m", "date": "$created_at"}},
            "count": {"$sum": 1},
        }},
        {"$sort": {"_id": 1}},
    ]
    drafts_monthly = {}
    async for doc in db.drafts.aggregate(pipeline_drafts_timeline):
        drafts_monthly[doc["_id"]] = doc["count"]

    # Build full 12-month timeline
    activity_timeline = []
    for i in range(12):
        month_date = now - timedelta(days=30 * (11 - i))
        month_key = month_date.strftime("%Y-%m")
        activity_timeline.append({
            "month": month_key,
            "papers": papers_monthly.get(month_key, 0),
            "drafts": drafts_monthly.get(month_key, 0),
        })

    return {
        "workspace_id": workspace_id,
        "workspace_name": workspace.get("name", ""),
        "summary": {
            "total_papers": total_papers,
            "indexed_papers": indexed_papers,
            "pending_papers": pending_papers,
            "processing_papers": processing_papers,
            "failed_papers": failed_papers,
            "total_drafts": total_drafts,
            "total_draft_versions": total_draft_versions,
            "total_members": len(members),
            "total_chat_sessions": total_chat_sessions,
        },
        "papers_by_source": papers_by_source,
        "contributors": contributors,
        "activity_timeline": activity_timeline,
    }
