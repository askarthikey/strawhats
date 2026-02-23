"""Tests for chat and citation functionality."""

import pytest
from app.utils.citations import parse_citations, replace_citations_with_numbers
from app.chat.prompts import build_context_block, build_rag_prompt


def test_parse_citations():
    text = "This is a fact [[CITE:abc123]] and another [[CITE:def456]]."
    citations = parse_citations(text)
    assert citations == ["abc123", "def456"]


def test_parse_citations_none():
    text = "No citations here."
    citations = parse_citations(text)
    assert citations == []


def test_parse_citations_duplicate():
    text = "Fact [[CITE:abc123]] repeated [[CITE:abc123]]."
    citations = parse_citations(text)
    assert citations == ["abc123", "abc123"]


def test_replace_citations_with_numbers():
    text = "Fact one [[CITE:abc123]] and fact two [[CITE:def456]]."
    citation_map = {"abc123": 1, "def456": 2}
    result = replace_citations_with_numbers(text, citation_map)
    assert "[1]" in result
    assert "[2]" in result
    assert "[[CITE:" not in result


def test_build_context_block():
    chunks = [
        {
            "chunk_id": "abc123",
            "paper_title": "Test Paper",
            "page_number": 5,
            "text": "Some chunk text here.",
            "score": 0.95,
        }
    ]
    context = build_context_block(chunks)
    assert "abc123" in context
    assert "Test Paper" in context
    assert "p.5" in context


def test_build_context_block_empty():
    assert "No relevant" in build_context_block([])


def test_build_rag_prompt():
    prompt = build_rag_prompt("What is ML?", "Context: ML is machine learning.", "default")
    assert "What is ML?" in prompt
    assert "Context: ML is machine learning." in prompt


def test_build_rag_prompt_with_template():
    prompt = build_rag_prompt("neural networks", "Context here", "summarize")
    assert "Main Findings" in prompt
    assert "neural networks" in prompt


def test_build_rag_prompt_with_history():
    history = [
        {"role": "user", "content": "What is AI?"},
        {"role": "assistant", "content": "AI is artificial intelligence."},
    ]
    prompt = build_rag_prompt("Tell me more", "Context", "default", history)
    assert "What is AI?" in prompt
    assert "Previous conversation" in prompt
