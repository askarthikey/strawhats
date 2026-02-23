"""Reference export service: BibTeX and RIS formats."""

from typing import List
from bson import ObjectId
from app.database import get_db


async def to_bibtex(paper_ids: List[str]) -> str:
    """Generate BibTeX string for given paper IDs."""
    db = get_db()
    entries = []

    for pid in paper_ids:
        try:
            paper = await db.papers.find_one({"_id": ObjectId(pid)})
        except Exception:
            continue
        if not paper:
            continue

        # Generate citation key
        first_author = paper.get("authors", ["Unknown"])[0].split()[-1].lower() if paper.get("authors") else "unknown"
        year = paper.get("year", "nd")
        key = f"{first_author}{year}"

        authors_str = " and ".join(paper.get("authors", ["Unknown"]))
        doi = paper.get("doi", "")
        venue = paper.get("venue", "")

        entry = f"""@article{{{key},
  title = {{{paper.get("title", "Untitled")}}},
  author = {{{authors_str}}},
  year = {{{year}}},
  journal = {{{venue}}},
  doi = {{{doi}}},
  abstract = {{{(paper.get("abstract", "") or "")[:500]}}},
}}"""
        entries.append(entry)

    return "\n\n".join(entries)


async def to_ris(paper_ids: List[str]) -> str:
    """Generate RIS string for given paper IDs."""
    db = get_db()
    entries = []

    for pid in paper_ids:
        try:
            paper = await db.papers.find_one({"_id": ObjectId(pid)})
        except Exception:
            continue
        if not paper:
            continue

        lines = [
            "TY  - JOUR",
            f"TI  - {paper.get('title', 'Untitled')}",
        ]

        for author in paper.get("authors", []):
            lines.append(f"AU  - {author}")

        if paper.get("year"):
            lines.append(f"PY  - {paper['year']}")
        if paper.get("venue"):
            lines.append(f"JO  - {paper['venue']}")
        if paper.get("doi"):
            lines.append(f"DO  - {paper['doi']}")
        if paper.get("abstract"):
            lines.append(f"AB  - {paper['abstract'][:500]}")

        lines.append("ER  -")
        entries.append("\n".join(lines))

    return "\n\n".join(entries)
