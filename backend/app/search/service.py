"""Search service: semantic, hybrid, and MMR retrieval."""

from typing import List, Dict, Optional
from datetime import datetime, timezone
from bson import ObjectId

from app.database import get_db
from app.embeddings.service import embed_text_cached
from app.utils.vector_store import query_similar
from app.chat.service import mmr_rerank
from app.search.schemas import SearchResult


async def semantic_search(
    query: str,
    workspace_id: str,
    top_k: int = 8,
    use_mmr: bool = True,
    year_from: int = None,
    year_to: int = None,
) -> tuple[List[SearchResult], float]:
    """
    Semantic search: embed query → Pinecone → resolve metadata.
    Deduplicates by paper_id (keeps best chunk per paper).
    Returns (results, search_time_ms).
    """
    start = datetime.now(timezone.utc)
    db = get_db()

    # Embed query
    query_vector = embed_text_cached(query)

    # Query Pinecone — fetch extra to allow dedup & MMR
    fetch_k = top_k * 5
    raw_results = query_similar(
        vector=query_vector,
        top_k=fetch_k,
        namespace=workspace_id,
    )

    # MMR reranking for diversity (always enabled)
    if use_mmr and len(raw_results) > top_k:
        raw_results = mmr_rerank(raw_results, query_vector, top_k=fetch_k)

    # Deduplicate by paper_id — keep only the best-scoring chunk per paper
    seen_papers = {}
    for r in raw_results:
        metadata = r.get("metadata", {})
        paper_id = metadata.get("paper_id", r["id"])
        score = r.get("score", 0)
        if paper_id not in seen_papers or score > seen_papers[paper_id].get("score", 0):
            seen_papers[paper_id] = r

    deduped_results = sorted(seen_papers.values(), key=lambda x: x.get("score", 0), reverse=True)

    # Resolve full metadata from MongoDB
    results = []
    for r in deduped_results[:top_k]:
        chunk_id = r["id"]
        metadata = r.get("metadata", {})
        paper_id = metadata.get("paper_id", "")

        # Get paper details
        paper = None
        if paper_id:
            try:
                paper = await db.papers.find_one({"_id": ObjectId(paper_id)})
            except Exception:
                pass

        # Apply year filter
        if paper and year_from and paper.get("year") and paper["year"] < year_from:
            continue
        if paper and year_to and paper.get("year") and paper["year"] > year_to:
            continue

        # Get chunk text with sentence-level context
        chunk_text = metadata.get("text_preview", "")
        try:
            chunk_doc = await db.chunks.find_one({"_id": ObjectId(chunk_id)})
            if chunk_doc:
                full_text = chunk_doc.get("text", chunk_text)
                # Extract 2-3 meaningful sentences as snippet
                sentences = [s.strip() for s in full_text.replace("\n", " ").split(".") if len(s.strip()) > 20]
                chunk_text = ". ".join(sentences[:3]) + "." if sentences else full_text[:300]
        except Exception:
            pass

        results.append(SearchResult(
            chunk_id=chunk_id,
            paper_id=paper_id,
            paper_title=paper.get("title", metadata.get("paper_title", "Unknown")) if paper else metadata.get("paper_title", "Unknown"),
            authors=paper.get("authors", []) if paper else [],
            year=paper.get("year") if paper else None,
            venue=paper.get("venue") if paper else None,
            page_number=metadata.get("page_number"),
            snippet=chunk_text[:500],
            score=r.get("score", 0),
            doi=paper.get("doi") if paper else None,
        ))

    search_time = (datetime.now(timezone.utc) - start).total_seconds() * 1000
    return results, search_time


async def hybrid_search(
    query: str,
    workspace_id: str,
    top_k: int = 10,
    semantic_weight: float = 0.7,
    year_from: int = None,
    year_to: int = None,
) -> tuple[List[SearchResult], float]:
    """
    Hybrid search: combine semantic (Pinecone) + keyword (MongoDB text search).
    """
    start = datetime.now(timezone.utc)
    db = get_db()

    # Semantic search
    semantic_results, _ = await semantic_search(
        query, workspace_id, top_k=top_k, year_from=year_from, year_to=year_to
    )

    # Keyword search via MongoDB text index
    keyword_filter = {
        "workspace_id": workspace_id,
        "$text": {"$search": query},
    }
    if year_from:
        keyword_filter["year"] = {"$gte": year_from}
    if year_to:
        keyword_filter.setdefault("year", {})
        if isinstance(keyword_filter["year"], dict):
            keyword_filter["year"]["$lte"] = year_to
        else:
            keyword_filter["year"] = {"$lte": year_to}

    keyword_results = []
    try:
        cursor = db.papers.find(
            keyword_filter,
            {"score": {"$meta": "textScore"}},
        ).sort([("score", {"$meta": "textScore"})]).limit(top_k)

        async for paper in cursor:
            # Get first chunk for snippet
            chunk = await db.chunks.find_one({"paper_id": str(paper["_id"])})
            snippet = chunk.get("text", paper.get("abstract", ""))[:300] if chunk else (paper.get("abstract", "") or "")[:300]

            keyword_results.append(SearchResult(
                chunk_id=str(chunk["_id"]) if chunk else "",
                paper_id=str(paper["_id"]),
                paper_title=paper.get("title", "Unknown"),
                authors=paper.get("authors", []),
                year=paper.get("year"),
                venue=paper.get("venue"),
                page_number=chunk.get("page_number") if chunk else None,
                snippet=snippet,
                score=paper.get("score", 0),  # text search score
                doi=paper.get("doi"),
            ))
    except Exception:
        pass  # Text index might not exist or query might fail

    # Merge and deduplicate
    seen_papers = set()
    merged = []

    # Add semantic results with weight
    for r in semantic_results:
        key = f"{r.paper_id}:{r.chunk_id}"
        if key not in seen_papers:
            seen_papers.add(key)
            r.score = r.score * semantic_weight
            merged.append(r)

    # Add keyword results with weight
    for r in keyword_results:
        key = f"{r.paper_id}:{r.chunk_id}"
        if key not in seen_papers:
            seen_papers.add(key)
            r.score = r.score * (1 - semantic_weight)
            merged.append(r)
        else:
            # Boost score if found in both
            for m in merged:
                if f"{m.paper_id}:{m.chunk_id}" == key:
                    m.score += r.score * (1 - semantic_weight)
                    break

    # Sort by combined score
    merged.sort(key=lambda x: x.score, reverse=True)

    search_time = (datetime.now(timezone.utc) - start).total_seconds() * 1000
    return merged[:top_k], search_time
