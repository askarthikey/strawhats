"""FAISS local vector store fallback for when Pinecone is unavailable."""

import os
import json
import numpy as np
from typing import List, Dict, Optional, Any

try:
    import faiss  # type: ignore
    FAISS_AVAILABLE = True
except ImportError:
    faiss = None  # type: ignore
    FAISS_AVAILABLE = False

EMBEDDING_DIM = 384
FAISS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "faiss_data")

# In-memory stores per namespace
_indexes: Dict[str, Any] = {}
_metadata_store: Dict[str, List[Dict]] = {}
_id_map: Dict[str, List[str]] = {}


def _ensure_dir():
    os.makedirs(FAISS_DIR, exist_ok=True)


def _index_path(namespace: str) -> str:
    safe = namespace.replace("/", "_") or "default"
    return os.path.join(FAISS_DIR, f"{safe}.index")


def _meta_path(namespace: str) -> str:
    safe = namespace.replace("/", "_") or "default"
    return os.path.join(FAISS_DIR, f"{safe}.meta.json")


def _load_namespace(namespace: str):
    """Load FAISS index and metadata from disk if available."""
    if namespace in _indexes:
        return

    idx_path = _index_path(namespace)
    meta_path = _meta_path(namespace)

    if os.path.exists(idx_path) and os.path.exists(meta_path):
        _indexes[namespace] = faiss.read_index(idx_path)
        with open(meta_path, "r") as f:
            data = json.load(f)
        _metadata_store[namespace] = data.get("metadata", [])
        _id_map[namespace] = data.get("ids", [])
    else:
        _indexes[namespace] = faiss.IndexFlatIP(EMBEDDING_DIM)
        _metadata_store[namespace] = []
        _id_map[namespace] = []


def _save_namespace(namespace: str):
    """Persist FAISS index and metadata to disk."""
    _ensure_dir()
    if namespace not in _indexes:
        return
    faiss.write_index(_indexes[namespace], _index_path(namespace))
    with open(_meta_path(namespace), "w") as f:
        json.dump({
            "ids": _id_map.get(namespace, []),
            "metadata": _metadata_store.get(namespace, []),
        }, f)


def is_available() -> bool:
    return FAISS_AVAILABLE


def upsert_chunks(chunks: List[Dict], namespace: str = "") -> int:
    """Upsert chunk vectors to FAISS."""
    if not FAISS_AVAILABLE:
        return 0

    _load_namespace(namespace)
    index = _indexes[namespace]
    ids = _id_map[namespace]
    metas = _metadata_store[namespace]

    vectors = []
    for c in chunks:
        vec = np.array(c["values"], dtype=np.float32)
        # Normalize for cosine similarity (IndexFlatIP)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm

        cid = c["id"]
        meta = c.get("metadata", {})

        # Check if ID already exists — update in place
        if cid in ids:
            idx = ids.index(cid)
            # FAISS doesn't support in-place update, but for small-scale fallback this is fine
            metas[idx] = meta
        else:
            ids.append(cid)
            metas.append(meta)
            vectors.append(vec)

    if vectors:
        mat = np.vstack(vectors).astype(np.float32)
        index.add(mat)

    _save_namespace(namespace)
    return len(chunks)


def query_similar(
    vector: List[float],
    top_k: int = 10,
    namespace: str = "",
    filter_dict: Optional[Dict] = None,
    include_metadata: bool = True,
) -> List[Dict]:
    """Query FAISS for similar vectors."""
    if not FAISS_AVAILABLE:
        return []

    _load_namespace(namespace)
    index = _indexes[namespace]
    ids = _id_map[namespace]
    metas = _metadata_store[namespace]

    if index.ntotal == 0:
        return []

    vec = np.array(vector, dtype=np.float32).reshape(1, -1)
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm

    # Search more than top_k to allow for filtering
    search_k = min(top_k * 3, index.ntotal)
    scores, indices = index.search(vec, search_k)

    matches = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0 or idx >= len(ids):
            continue

        meta = metas[idx] if idx < len(metas) else {}

        # Apply metadata filter
        if filter_dict:
            match = True
            for key, val in filter_dict.items():
                if isinstance(val, dict) and "$in" in val:
                    if meta.get(key) not in val["$in"]:
                        match = False
                        break
                elif meta.get(key) != val:
                    match = False
                    break
            if not match:
                continue

        result = {"id": ids[idx], "score": float(score)}
        if include_metadata:
            result["metadata"] = meta
        matches.append(result)

        if len(matches) >= top_k:
            break

    return matches


def delete_by_paper(paper_id: str, namespace: str = ""):
    """Delete all vectors for a given paper (marks as deleted, rebuilds)."""
    if not FAISS_AVAILABLE:
        return

    _load_namespace(namespace)
    ids = _id_map[namespace]
    metas = _metadata_store[namespace]

    # Find indices to keep
    keep_idx = [i for i, m in enumerate(metas) if m.get("paper_id") != paper_id]

    if len(keep_idx) == len(ids):
        return  # Nothing to delete

    # Rebuild index
    index = _indexes[namespace]
    if len(keep_idx) > 0:
        # Reconstruct kept vectors
        old_vectors = np.array([index.reconstruct(i) for i in keep_idx], dtype=np.float32)
        new_index = faiss.IndexFlatIP(EMBEDDING_DIM)
        new_index.add(old_vectors)
        _indexes[namespace] = new_index
    else:
        _indexes[namespace] = faiss.IndexFlatIP(EMBEDDING_DIM)

    _id_map[namespace] = [ids[i] for i in keep_idx]
    _metadata_store[namespace] = [metas[i] for i in keep_idx]
    _save_namespace(namespace)


def delete_namespace(namespace: str):
    """Delete an entire namespace."""
    if namespace in _indexes:
        del _indexes[namespace]
    if namespace in _id_map:
        del _id_map[namespace]
    if namespace in _metadata_store:
        del _metadata_store[namespace]

    # Remove files
    for path in [_index_path(namespace), _meta_path(namespace)]:
        if os.path.exists(path):
            os.remove(path)


def get_stats() -> dict:
    """Get FAISS index statistics."""
    if not FAISS_AVAILABLE:
        return {"status": "faiss not installed"}

    stats = {"status": "active", "namespaces": {}}
    for ns, index in _indexes.items():
        stats["namespaces"][ns] = {"vector_count": index.ntotal}
    return stats
