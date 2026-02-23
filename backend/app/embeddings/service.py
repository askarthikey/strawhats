"""Embedding service using sentence-transformers."""

from typing import List
from functools import lru_cache
import numpy as np

_model = None
EMBEDDING_DIM = 384
MODEL_NAME = "all-MiniLM-L6-v2"


def get_model():
    """Load embedding model (singleton, cached)."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def embed_text(text: str) -> List[float]:
    """Embed a single text string. Returns 384-dim vector."""
    model = get_model()
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()


def embed_batch(texts: List[str], batch_size: int = 32) -> List[List[float]]:
    """Embed a batch of texts. Returns list of 384-dim vectors."""
    if not texts:
        return []
    model = get_model()
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return embeddings.tolist()


# Simple LRU cache for repeated queries
_query_cache = {}
_CACHE_MAX = 1000


def embed_text_cached(text: str) -> List[float]:
    """Embed with LRU caching for repeated queries."""
    if text in _query_cache:
        return _query_cache[text]

    result = embed_text(text)

    if len(_query_cache) >= _CACHE_MAX:
        # Remove oldest entry
        oldest_key = next(iter(_query_cache))
        del _query_cache[oldest_key]

    _query_cache[text] = result
    return result


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    a_arr = np.array(a)
    b_arr = np.array(b)
    return float(np.dot(a_arr, b_arr) / (np.linalg.norm(a_arr) * np.linalg.norm(b_arr)))
