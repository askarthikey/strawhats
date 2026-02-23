"""Tests for paper ingestion and metadata normalization."""

import pytest
from app.papers.schemas import PaperMetadata
from app.utils.helpers import generate_dedup_hash


def test_paper_metadata_creation():
    paper = PaperMetadata(
        title="Test Paper",
        authors=["John Doe", "Jane Smith"],
        doi="10.1234/test",
        year=2024,
        venue="Test Journal",
        abstract="This is a test abstract.",
        source="openalex",
    )
    assert paper.title == "Test Paper"
    assert len(paper.authors) == 2
    assert paper.doi == "10.1234/test"


def test_paper_metadata_defaults():
    paper = PaperMetadata(title="Minimal Paper")
    assert paper.authors == []
    assert paper.doi is None
    assert paper.year is None
    assert paper.source is None


def test_dedup_hash_consistency():
    hash1 = generate_dedup_hash("Test Paper", ["John Doe"], 2024)
    hash2 = generate_dedup_hash("Test Paper", ["John Doe"], 2024)
    assert hash1 == hash2


def test_dedup_hash_case_insensitive():
    hash1 = generate_dedup_hash("Test Paper", ["John Doe"], 2024)
    hash2 = generate_dedup_hash("test paper", ["john doe"], 2024)
    assert hash1 == hash2


def test_dedup_hash_author_order_invariant():
    hash1 = generate_dedup_hash("Test", ["Alice", "Bob"], 2024)
    hash2 = generate_dedup_hash("Test", ["Bob", "Alice"], 2024)
    assert hash1 == hash2


def test_dedup_hash_different_papers():
    hash1 = generate_dedup_hash("Paper A", ["Author 1"], 2024)
    hash2 = generate_dedup_hash("Paper B", ["Author 2"], 2024)
    assert hash1 != hash2
