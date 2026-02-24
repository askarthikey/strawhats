"""Unified vector store: Pinecone primary, FAISS fallback."""

from typing import List, Dict, Optional
from app.utils import pinecone_client, faiss_client


def _pinecone_available() -> bool:
    """Check if Pinecone is connected."""
    try:
        index = pinecone_client.get_index()
        return index is not None
    except Exception:
        return False


def upsert_chunks(chunks: List[Dict], namespace: str = "") -> int:
    """Upsert to Pinecone, fall back to FAISS."""
    if _pinecone_available():
        try:
            count = pinecone_client.upsert_chunks(chunks, namespace)
            # Also mirror to FAISS for resilience
            if faiss_client.is_available():
                try:
                    faiss_client.upsert_chunks(chunks, namespace)
                except Exception:
                    pass
            return count
        except Exception as e:
            print(f"Pinecone upsert failed, trying FAISS: {e}")

    if faiss_client.is_available():
        return faiss_client.upsert_chunks(chunks, namespace)

    print("WARNING: No vector store available!")
    return 0


def query_similar(
    vector: List[float],
    top_k: int = 10,
    namespace: str = "",
    filter_dict: Optional[Dict] = None,
    include_metadata: bool = True,
) -> List[Dict]:
    """Query Pinecone, fall back to FAISS."""
    if _pinecone_available():
        try:
            return pinecone_client.query_similar(
                vector, top_k, namespace, filter_dict, include_metadata
            )
        except Exception as e:
            print(f"Pinecone query failed, trying FAISS: {e}")

    if faiss_client.is_available():
        return faiss_client.query_similar(
            vector, top_k, namespace, filter_dict, include_metadata
        )

    return []


def delete_by_paper(paper_id: str, namespace: str = ""):
    """Delete from both stores."""
    try:
        pinecone_client.delete_by_paper(paper_id, namespace)
    except Exception:
        pass

    if faiss_client.is_available():
        try:
            faiss_client.delete_by_paper(paper_id, namespace)
        except Exception:
            pass


def delete_namespace(namespace: str):
    """Delete namespace from both stores."""
    try:
        pinecone_client.delete_namespace(namespace)
    except Exception:
        pass

    if faiss_client.is_available():
        try:
            faiss_client.delete_namespace(namespace)
        except Exception:
            pass


def get_stats() -> dict:
    """Get stats from all stores."""
    stats = {}
    try:
        stats["pinecone"] = pinecone_client.get_index_stats()
    except Exception:
        stats["pinecone"] = {"status": "disconnected"}

    stats["faiss"] = faiss_client.get_stats()
    return stats
