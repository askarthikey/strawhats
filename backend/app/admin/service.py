"""Admin service: health checks and metrics."""

from app.database import get_db
from app.utils.vector_store import get_stats as get_index_stats
from app.llm import ollama_client, gemini_client
from app.config import settings


async def health_check() -> dict:
    """Check health of all services."""
    checks = {}

    # MongoDB
    try:
        db = get_db()
        await db.command("ping")
        checks["mongodb"] = {"status": "healthy"}
    except Exception as e:
        checks["mongodb"] = {"status": "unhealthy", "error": str(e)}

    # Pinecone
    try:
        stats = get_index_stats()
        # Convert Pinecone stats object to plain dict
        if hasattr(stats, "to_dict"):
            stats = stats.to_dict()
        elif hasattr(stats, "__dict__"):
            stats = {k: v for k, v in stats.__dict__.items() if not k.startswith("_")}
        checks["pinecone"] = {"status": "healthy", "total_vectors": stats.get("total_vector_count", stats.get("totalVectorCount", 0))}
    except Exception as e:
        checks["pinecone"] = {"status": "unhealthy", "error": str(e)}

    # Ollama
    try:
        healthy = await ollama_client.check_health()
        checks["ollama"] = {"status": "healthy" if healthy else "unavailable"}
    except Exception as e:
        checks["ollama"] = {"status": "unhealthy", "error": str(e)}

    # Gemini
    checks["gemini"] = {
        "status": "configured" if settings.GEMINI_API_KEY else "not_configured"
    }

    # Cloudinary
    checks["cloudinary"] = {
        "status": "configured" if settings.CLOUDINARY_CLOUD_NAME and settings.CLOUDINARY_API_KEY else "not_configured"
    }

    overall = all(
        c.get("status") in ("healthy", "configured", "unavailable")
        for c in checks.values()
    )

    return {
        "status": "healthy" if overall else "degraded",
        "services": checks,
    }


async def get_metrics() -> dict:
    """Get application metrics."""
    db = get_db()

    try:
        metrics = {
            "users": await db.users.count_documents({}),
            "workspaces": await db.workspaces.count_documents({}),
            "papers": await db.papers.count_documents({}),
            "chunks": await db.chunks.count_documents({}),
            "chat_logs": await db.chat_logs.count_documents({}),
            "drafts": await db.drafts.count_documents({}),
        }

        # Paper status breakdown
        for status in ["pending", "processing", "indexed", "failed"]:
            metrics[f"papers_{status}"] = await db.papers.count_documents({"status": status})

        # Recent chat logs for latency metrics
        pipeline = [
            {"$sort": {"created_at": -1}},
            {"$limit": 100},
            {"$group": {
                "_id": None,
                "avg_retrieval_time": {"$avg": "$retrieval_trace.retrieval_time_s"},
                "avg_generation_time": {"$avg": "$retrieval_trace.generation_time_s"},
                "avg_chunks_retrieved": {"$avg": "$retrieval_trace.chunks_retrieved"},
            }},
        ]
        try:
            async for doc in db.chat_logs.aggregate(pipeline):
                metrics["avg_retrieval_time_s"] = doc.get("avg_retrieval_time", 0)
                metrics["avg_generation_time_s"] = doc.get("avg_generation_time", 0)
                metrics["avg_chunks_retrieved"] = doc.get("avg_chunks_retrieved", 0)
        except Exception:
            pass

        return metrics
    except Exception as e:
        return {"error": str(e)}
