"""Tests for text chunking and PDF processing."""

import pytest
from app.papers.processing import chunk_text, count_tokens, _split_sentences


def test_count_tokens():
    text = "Hello world this is a test"
    count = count_tokens(text)
    assert count > 0


def test_split_sentences():
    text = "First sentence. Second sentence. Third sentence."
    sentences = _split_sentences(text)
    assert len(sentences) == 3


def test_chunk_text_basic():
    pages = [
        {
            "page_number": 1,
            "text": " ".join(["This is sentence number {}.".format(i) for i in range(100)]),
            "char_start": 0,
            "char_end": 3000,
        }
    ]
    chunks = chunk_text(pages, target_tokens=50, overlap_tokens=10)
    assert len(chunks) > 1
    assert all(c.chunk_index >= 0 for c in chunks)
    assert all(c.page_number == 1 for c in chunks)


def test_chunk_text_empty():
    pages = [{"page_number": 1, "text": "", "char_start": 0, "char_end": 0}]
    chunks = chunk_text(pages, target_tokens=100, overlap_tokens=20)
    assert len(chunks) == 0


def test_chunk_text_single_sentence():
    pages = [{"page_number": 1, "text": "Single sentence.", "char_start": 0, "char_end": 16}]
    chunks = chunk_text(pages, target_tokens=100, overlap_tokens=20)
    assert len(chunks) == 1
    assert chunks[0].text == "Single sentence."


def test_chunk_checksum():
    pages = [{"page_number": 1, "text": "Test text for checksum.", "char_start": 0, "char_end": 23}]
    chunks = chunk_text(pages, target_tokens=100, overlap_tokens=20)
    assert chunks[0].checksum  # Non-empty checksum
    assert len(chunks[0].checksum) == 32  # MD5 hex


def test_chunk_overlap():
    # Create text long enough to need multiple chunks
    long_text = ". ".join([f"Sentence {i} with some padding words to make it longer" for i in range(200)])
    pages = [{"page_number": 1, "text": long_text, "char_start": 0, "char_end": len(long_text)}]
    chunks = chunk_text(pages, target_tokens=30, overlap_tokens=5)

    # Should have multiple chunks
    assert len(chunks) > 1

    # Chunk indices should be sequential
    for i, chunk in enumerate(chunks):
        assert chunk.chunk_index == i
