"""Tests for search functionality."""

import pytest
from app.chat.service import mmr_rerank


def test_mmr_rerank_empty():
    results = mmr_rerank([], [0.1] * 384, top_k=5)
    assert results == []


def test_mmr_rerank_fewer_than_topk():
    results = [
        {"id": "1", "score": 0.9, "metadata": {}},
        {"id": "2", "score": 0.8, "metadata": {}},
    ]
    reranked = mmr_rerank(results, [0.1] * 384, top_k=5)
    assert len(reranked) == 2


def test_mmr_rerank_selects_topk():
    results = [
        {"id": str(i), "score": 1.0 - i * 0.1, "metadata": {}}
        for i in range(20)
    ]
    reranked = mmr_rerank(results, [0.1] * 384, top_k=5)
    assert len(reranked) == 5


def test_mmr_rerank_most_relevant_first():
    results = [
        {"id": "1", "score": 0.5, "metadata": {}},
        {"id": "2", "score": 0.9, "metadata": {}},
        {"id": "3", "score": 0.7, "metadata": {}},
    ]
    reranked = mmr_rerank(results, [0.1] * 384, top_k=3)
    assert reranked[0]["id"] == "2"  # Most relevant first
