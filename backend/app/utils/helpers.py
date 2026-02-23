"""Common utility functions."""

from datetime import datetime, timezone
from bson import ObjectId
from typing import Any, Dict


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def serialize_doc(doc: Dict) -> Dict:
    """Convert MongoDB document for JSON serialization."""
    if doc is None:
        return None
    result = {}
    for key, value in doc.items():
        if key == "_id":
            result["id"] = str(value)
        elif isinstance(value, ObjectId):
            result[key] = str(value)
        elif isinstance(value, datetime):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result


def generate_dedup_hash(title: str, authors: list, year: int = None) -> str:
    """Generate a deduplication hash from title + authors + year."""
    import hashlib
    normalized_title = title.lower().strip()
    normalized_authors = ",".join(sorted(a.lower().strip() for a in authors))
    key = f"{normalized_title}|{normalized_authors}|{year or ''}"
    return hashlib.sha256(key.encode()).hexdigest()
