"""RAG pipeline: retrieve → rerank → generate with citations."""

from typing import AsyncGenerator, List, Dict, Optional
from datetime import datetime, timezone
from bson import ObjectId
import numpy as np

from app.database import get_db
from app.embeddings.service import embed_text_cached, cosine_similarity
from app.utils.pinecone_client import query_similar
from app.utils.citations import parse_citations, resolve_citations
from app.chat.prompts import RAG_SYSTEM_PROMPT, build_context_block, build_rag_prompt
from app.llm.provider import get_llm_provider
from app.utils.helpers import utc_now


async def rag_generate(
    question: str,
    workspace_id: str,
    user_id: str,
    chat_history: list = None,
    template: str = "default",
    provider_name: str = "ollama",
    top_k: int = 10,
    temperature: float = 0.0,
    use_mmr: bool = False,
) -> AsyncGenerator[dict, None]:
    """
    Full RAG pipeline:
    1. Embed question
    2. Retrieve top-k chunks from Pinecone
    3. Optional MMR rerank for diversity
    4. Build prompt with context
    5. Stream LLM generation
    6. Parse and resolve citations
    7. Store chat log
    8. Yield {type, token, citations, done} events
    """
    db = get_db()
    retrieval_start = datetime.now(timezone.utc)

    # Step 1: Embed the question
    query_vector = embed_text_cached(question)

    # Step 2: Retrieve from Pinecone
    raw_results = query_similar(
        vector=query_vector,
        top_k=top_k * 2 if use_mmr else top_k,  # Get more for MMR
        namespace=workspace_id,
    )

    # Step 3: MMR reranking if requested
    if use_mmr and raw_results:
        raw_results = mmr_rerank(raw_results, query_vector, top_k=top_k)
    else:
        raw_results = raw_results[:top_k]

    retrieval_time = (datetime.now(timezone.utc) - retrieval_start).total_seconds()

    # Enrich results with full chunk text from MongoDB
    enriched_chunks = []
    for r in raw_results:
        chunk_id = r["id"]
        metadata = r.get("metadata", {})

        # Try to get full text from MongoDB
        try:
            chunk_doc = await db.chunks.find_one({"_id": ObjectId(chunk_id)})
            if chunk_doc:
                enriched_chunks.append({
                    "chunk_id": chunk_id,
                    "text": chunk_doc.get("text", metadata.get("text_preview", "")),
                    "paper_title": metadata.get("paper_title", ""),
                    "page_number": chunk_doc.get("page_number", metadata.get("page_number", 0)),
                    "paper_id": chunk_doc.get("paper_id", metadata.get("paper_id", "")),
                    "score": r.get("score", 0),
                })
            else:
                enriched_chunks.append({
                    "chunk_id": chunk_id,
                    "text": metadata.get("text_preview", ""),
                    "paper_title": metadata.get("paper_title", ""),
                    "page_number": metadata.get("page_number", 0),
                    "paper_id": metadata.get("paper_id", ""),
                    "score": r.get("score", 0),
                })
        except Exception:
            enriched_chunks.append({
                "chunk_id": chunk_id,
                "text": metadata.get("text_preview", ""),
                "paper_title": metadata.get("paper_title", ""),
                "page_number": metadata.get("page_number", 0),
                "paper_id": metadata.get("paper_id", ""),
                "score": r.get("score", 0),
            })

    # Step 4: Build prompt
    context_block = build_context_block(enriched_chunks)
    history_dicts = [{"role": m.get("role", "user"), "content": m.get("content", "")} for m in (chat_history or [])]
    prompt = build_rag_prompt(question, context_block, template, history_dicts)

    # Step 5: Get LLM provider
    llm = await get_llm_provider(provider_name)

    # Step 6: Stream generation
    generation_start = datetime.now(timezone.utc)
    full_response = ""

    try:
        async for token in llm.generate_stream(
            prompt=prompt,
            system_prompt=RAG_SYSTEM_PROMPT,
            temperature=temperature,
        ):
            full_response += token
            yield {
                "type": "token",
                "token": token,
            }
    except Exception as e:
        yield {
            "type": "error",
            "error": f"LLM generation failed: {str(e)}",
        }
        return

    generation_time = (datetime.now(timezone.utc) - generation_start).total_seconds()

    # Step 7: Parse and resolve citations
    cited_chunk_ids = parse_citations(full_response)
    citations = await resolve_citations(cited_chunk_ids, db)

    # Yield citations
    if citations:
        yield {
            "type": "citations",
            "citations": citations,
        }

    # Step 8: Store chat log
    chat_log = {
        "workspace_id": workspace_id,
        "user_id": user_id,
        "question": question,
        "answer": full_response,
        "template": template,
        "provider": llm.name,
        "used_chunk_ids": [c["chunk_id"] for c in enriched_chunks],
        "cited_chunk_ids": cited_chunk_ids,
        "citations": citations,
        "model_params": {
            "temperature": temperature,
            "top_k": top_k,
            "use_mmr": use_mmr,
        },
        "retrieval_trace": {
            "retrieval_time_s": retrieval_time,
            "generation_time_s": generation_time,
            "chunks_retrieved": len(enriched_chunks),
            "chunks_cited": len(cited_chunk_ids),
        },
        "created_at": utc_now(),
    }
    await db.chat_logs.insert_one(chat_log)

    # Final done event
    yield {
        "type": "done",
        "full_response": full_response,
        "metadata": {
            "retrieval_time": retrieval_time,
            "generation_time": generation_time,
            "chunks_used": len(enriched_chunks),
            "citations_count": len(citations),
            "provider": llm.name,
        },
    }


def mmr_rerank(
    results: List[Dict],
    query_vector: List[float],
    top_k: int = 10,
    lambda_param: float = 0.7,
) -> List[Dict]:
    """
    Maximal Marginal Relevance reranking for diversity.
    lambda_param: balance between relevance (1.0) and diversity (0.0).
    """
    if not results or len(results) <= top_k:
        return results

    selected = []
    remaining = list(range(len(results)))

    # Select the most relevant first
    remaining.sort(key=lambda i: results[i].get("score", 0), reverse=True)
    selected.append(remaining.pop(0))

    while len(selected) < top_k and remaining:
        best_score = -float("inf")
        best_idx = -1

        for idx in remaining:
            # Relevance to query
            relevance = results[idx].get("score", 0)

            # Max similarity to already selected
            max_sim = 0
            for sel_idx in selected:
                # Use score as proxy for similarity
                sim = abs(results[idx].get("score", 0) - results[sel_idx].get("score", 0))
                max_sim = max(max_sim, 1 - sim)

            mmr_score = lambda_param * relevance - (1 - lambda_param) * max_sim

            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = idx

        if best_idx >= 0:
            remaining.remove(best_idx)
            selected.append(best_idx)
        else:
            break

    return [results[i] for i in selected]


async def get_chat_history(workspace_id: str, limit: int = 50) -> List[dict]:
    """Get chat history for a workspace."""
    db = get_db()
    cursor = db.chat_logs.find(
        {"workspace_id": workspace_id}
    ).sort("created_at", -1).limit(limit)

    logs = []
    async for doc in cursor:
        doc["id"] = str(doc["_id"])
        del doc["_id"]
        logs.append(doc)

    return list(reversed(logs))


async def clear_chat_history(workspace_id: str) -> int:
    """Clear chat history for a workspace. Returns count deleted."""
    db = get_db()
    result = await db.chat_logs.delete_many({"workspace_id": workspace_id})
    return result.deleted_count
