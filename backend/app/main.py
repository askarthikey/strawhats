"""ResearchHub AI — FastAPI Application Entry Point."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.config import settings
from app.database import connect_db, close_db
from app.utils.pinecone_client import init_pinecone

# Import routers
from app.auth.router import router as auth_router
from app.papers.router import router as papers_router
from app.search.router import router as search_router
from app.chat.router import router as chat_router
from app.workspaces.router import router as workspaces_router
from app.drafts.router import router as drafts_router
from app.drafts.websocket import router as drafts_ws_router
from app.drafts.ai_router import router as drafts_ai_router
from app.references.router import router as references_router
from app.latex.router import router as latex_router
from app.admin.router import router as admin_router
from app.papers.status_ws import router as papers_ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    # Startup
    print(f"🚀 Starting {settings.APP_NAME}...")
    try:
        await connect_db()
        print("✅ MongoDB connected")
    except Exception as e:
        print(f"⚠️  MongoDB connection failed (will retry on use): {e}")

    # Initialize FAISS (primary vector store)
    try:
        from app.utils.faiss_client import _ensure_dir, FAISS_AVAILABLE
        _ensure_dir()
        if FAISS_AVAILABLE:
            print("✅ FAISS vector store ready (primary)")
        else:
            print("⚠️  FAISS not available — install faiss-cpu for local vector store")
    except Exception as e:
        print(f"⚠️  FAISS init failed: {e}")

    # Initialize Pinecone (fallback/mirror)
    try:
        init_pinecone()
        print("✅ Pinecone initialized (fallback)")
    except Exception as e:
        print(f"⚠️  Pinecone init skipped (FAISS is primary): {e}")

    # Pre-load embedding model in background
    try:
        from app.embeddings.service import get_model
        get_model()
        print("✅ Embedding model loaded")
    except Exception as e:
        print(f"⚠️  Embedding model will load on first use: {e}")

    # Ensure Supabase Storage connectivity
    try:
        from app.storage.supabase_client import ensure_storage
        await ensure_storage()
        print("✅ Supabase storage ready")
    except Exception as e:
        print(f"⚠️  Supabase storage setup deferred: {e}")

    print(f"✅ {settings.APP_NAME} is ready!")
    yield

    # Shutdown
    print("🔄 Shutting down...")
    await close_db()
    print("✅ Shutdown complete")


app = FastAPI(
    title=settings.APP_NAME,
    description="Agentic research assistant with RAG-powered citation-grounded answers",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth_router, prefix="/api")
app.include_router(papers_router, prefix="/api")
app.include_router(search_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(workspaces_router, prefix="/api")
app.include_router(drafts_router, prefix="/api")
app.include_router(drafts_ws_router)  # WebSocket routes (no prefix)
app.include_router(papers_ws_router)  # Paper status WebSocket (no prefix)
app.include_router(drafts_ai_router, prefix="/api")
app.include_router(references_router, prefix="/api")
app.include_router(latex_router, prefix="/api")
app.include_router(admin_router, prefix="/api")


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": "1.0.0",
        "docs": "/docs",
    }


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
