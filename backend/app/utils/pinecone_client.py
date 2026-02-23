"""Pinecone vector store client."""

from pinecone import Pinecone, ServerlessSpec
from typing import List, Dict, Optional
from app.config import settings

_pc: Pinecone = None
_index = None

EMBEDDING_DIM = 384


def init_pinecone():
    """Initialize Pinecone client and ensure index exists."""
    global _pc, _index

    if not settings.PINECONE_API_KEY:
        print("WARNING: PINECONE_API_KEY not set. Vector search disabled.")
        return

    _pc = Pinecone(api_key=settings.PINECONE_API_KEY)

    # Check if index exists, create if not
    existing = [idx.name for idx in _pc.list_indexes()]
    if settings.PINECONE_INDEX not in existing:
        _pc.create_index(
            name=settings.PINECONE_INDEX,
            dimension=EMBEDDING_DIM,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )

    _index = _pc.Index(settings.PINECONE_INDEX)
    return _index


def get_index():
    """Get the Pinecone index."""
    global _index
    if _index is None:
        init_pinecone()
    return _index


def upsert_chunks(
    chunks: List[Dict],
    namespace: str = "",
) -> int:
    """
    Upsert chunk vectors to Pinecone.
    Each chunk dict: {id, values, metadata}
    metadata: {paper_id, chunk_index, page_number, text_preview, paper_title}
    Returns number of vectors upserted.
    """
    index = get_index()
    if index is None:
        return 0

    # Batch upsert (Pinecone recommends batches of 100)
    batch_size = 100
    total = 0
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        vectors = [
            {
                "id": c["id"],
                "values": c["values"],
                "metadata": c.get("metadata", {}),
            }
            for c in batch
        ]
        index.upsert(vectors=vectors, namespace=namespace)
        total += len(vectors)

    return total


def query_similar(
    vector: List[float],
    top_k: int = 10,
    namespace: str = "",
    filter_dict: Optional[Dict] = None,
    include_metadata: bool = True,
) -> List[Dict]:
    """
    Query Pinecone for similar vectors.
    Returns list of {id, score, metadata}.
    """
    index = get_index()
    if index is None:
        return []

    kwargs = {
        "vector": vector,
        "top_k": top_k,
        "namespace": namespace,
        "include_metadata": include_metadata,
    }
    if filter_dict:
        kwargs["filter"] = filter_dict

    results = index.query(**kwargs)

    matches = []
    for match in results.get("matches", []):
        matches.append({
            "id": match["id"],
            "score": match["score"],
            "metadata": match.get("metadata", {}),
        })
    return matches


def delete_by_paper(paper_id: str, namespace: str = ""):
    """Delete all vectors for a given paper."""
    index = get_index()
    if index is None:
        return

    # Delete by metadata filter
    index.delete(
        filter={"paper_id": paper_id},
        namespace=namespace,
    )


def delete_namespace(namespace: str):
    """Delete an entire namespace."""
    index = get_index()
    if index is None:
        return
    index.delete(delete_all=True, namespace=namespace)


def get_index_stats() -> dict:
    """Get index statistics."""
    index = get_index()
    if index is None:
        return {"status": "disconnected"}
    return index.describe_index_stats()
