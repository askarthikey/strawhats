"""Citation parsing and resolution utilities."""

import re
from typing import List, Dict, Optional
from bson import ObjectId


CITE_PATTERN = re.compile(r"\[\[CITE:([\w]+)\]\]")


def parse_citations(text: str) -> List[str]:
    """Extract all [[CITE:chunk_id]] from text. Returns list of chunk_ids."""
    return CITE_PATTERN.findall(text)


def replace_citations_with_numbers(text: str, citation_map: Dict[str, int]) -> str:
    """Replace [[CITE:chunk_id]] with [1], [2], etc."""
    def replacer(match):
        chunk_id = match.group(1)
        num = citation_map.get(chunk_id, "?")
        return f"[{num}]"
    return CITE_PATTERN.sub(replacer, text)


async def resolve_citations(chunk_ids: List[str], db) -> List[Dict]:
    """
    Resolve chunk IDs to full citation metadata.
    Returns list of {chunk_id, paper_id, title, page, snippet, score}.
    """
    if not chunk_ids:
        return []

    citations = []
    seen = set()

    for chunk_id in chunk_ids:
        if chunk_id in seen:
            continue
        seen.add(chunk_id)

        # Find chunk in MongoDB
        chunk = await db.chunks.find_one({"_id": ObjectId(chunk_id)})
        if not chunk:
            # Try finding by chunk string id
            chunk = await db.chunks.find_one({"chunk_id": chunk_id})
        if not chunk:
            continue

        # Get paper metadata
        paper_id = chunk.get("paper_id")
        paper = None
        if paper_id:
            try:
                paper = await db.papers.find_one({"_id": ObjectId(paper_id)})
            except Exception:
                paper = await db.papers.find_one({"_id": paper_id})

        snippet = chunk.get("text", "")[:200]

        citations.append({
            "chunk_id": chunk_id,
            "paper_id": str(paper_id) if paper_id else None,
            "title": paper.get("title", "Unknown") if paper else "Unknown",
            "authors": paper.get("authors", []) if paper else [],
            "page": chunk.get("page_number"),
            "snippet": snippet,
            "year": paper.get("year") if paper else None,
            "doi": paper.get("doi") if paper else None,
        })

    return citations


def format_citation_for_display(citation: Dict, index: int) -> str:
    """Format a citation for display in the UI."""
    authors = citation.get("authors", [])
    first_author = authors[0] if authors else "Unknown"
    year = citation.get("year", "n.d.")
    title = citation.get("title", "Untitled")
    return f"[{index}] {first_author} ({year}). {title}"
