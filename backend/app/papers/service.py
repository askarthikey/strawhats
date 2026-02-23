"""Paper service: orchestrates ingestion, processing, and indexing."""

from typing import List, Optional
from datetime import datetime, timezone
from bson import ObjectId
from fastapi import UploadFile, BackgroundTasks

from app.database import get_db
from app.papers.schemas import PaperMetadata, PaperResponse, PaperStatus, ChunkData
from app.papers.ingestion import (
    search_openalex, search_crossref, search_arxiv, search_pubmed, fetch_unpaywall_pdf,
)
from app.papers.processing import extract_text_from_pdf, chunk_text
from app.embeddings.service import embed_batch
from app.utils.pinecone_client import upsert_chunks, delete_by_paper
from app.utils.helpers import utc_now, generate_dedup_hash, serialize_doc
from app.storage.cloudinary_client import upload_pdf as cloud_upload, get_pdf_url, delete_pdf
import httpx


SEARCH_FUNCTIONS = {
    "openalex": search_openalex,
    "crossref": search_crossref,
    "arxiv": search_arxiv,
    "pubmed": search_pubmed,
}


async def search_external(query: str, source: str = "openalex", limit: int = 10) -> List[PaperMetadata]:
    """Search external APIs for papers."""
    search_fn = SEARCH_FUNCTIONS.get(source, search_openalex)
    return await search_fn(query, limit)


async def import_paper(
    metadata: PaperMetadata,
    workspace_id: str,
    user_id: str,
    background_tasks: BackgroundTasks = None,
) -> dict:
    """Import a paper into the workspace."""
    db = get_db()

    # Dedup check by DOI
    if metadata.doi:
        existing = await db.papers.find_one({
            "doi": metadata.doi,
            "workspace_id": workspace_id,
        })
        if existing:
            return serialize_doc(existing)

    # Dedup check by hash
    dedup_hash = generate_dedup_hash(metadata.title, metadata.authors, metadata.year)
    existing = await db.papers.find_one({
        "dedup_hash": dedup_hash,
        "workspace_id": workspace_id,
    })
    if existing:
        return serialize_doc(existing)

    # Create paper document
    paper_doc = {
        "title": metadata.title,
        "authors": metadata.authors,
        "doi": metadata.doi,
        "year": metadata.year,
        "venue": metadata.venue,
        "abstract": metadata.abstract,
        "pdf_url": metadata.pdf_url,
        "license": metadata.license,
        "source": metadata.source,
        "workspace_id": workspace_id,
        "added_by": user_id,
        "status": PaperStatus.PENDING,
        "storage_path": None,
        "chunk_count": 0,
        "dedup_hash": dedup_hash,
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    result = await db.papers.insert_one(paper_doc)
    paper_id = str(result.inserted_id)
    paper_doc["_id"] = result.inserted_id

    # Process in background if PDF available
    if metadata.pdf_url and background_tasks:
        background_tasks.add_task(
            _process_paper_pdf, paper_id, metadata.pdf_url, workspace_id
        )
    elif metadata.doi and background_tasks:
        # Try to find OA PDF
        background_tasks.add_task(
            _try_fetch_and_process, paper_id, metadata.doi, workspace_id
        )

    return serialize_doc(paper_doc)


async def upload_paper(
    file: UploadFile,
    workspace_id: str,
    user_id: str,
    title: str = None,
    background_tasks: BackgroundTasks = None,
) -> dict:
    """Upload and process a PDF file."""
    db = get_db()

    file_bytes = await file.read()
    filename = file.filename or "upload.pdf"

    # Create paper doc
    paper_doc = {
        "title": title or filename.replace(".pdf", ""),
        "authors": [],
        "doi": None,
        "year": None,
        "venue": None,
        "abstract": None,
        "pdf_url": None,
        "source": "upload",
        "workspace_id": workspace_id,
        "added_by": user_id,
        "status": PaperStatus.PROCESSING,
        "storage_path": None,
        "chunk_count": 0,
        "dedup_hash": None,
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    result = await db.papers.insert_one(paper_doc)
    paper_id = str(result.inserted_id)

    # Upload to Cloudinary
    try:
        storage_path = cloud_upload(file_bytes, paper_id, filename)
        await db.papers.update_one(
            {"_id": result.inserted_id},
            {"$set": {"storage_path": storage_path}},
        )
    except Exception as e:
        print(f"Cloudinary upload failed: {e}")
        storage_path = None

    # Process PDF in background
    if background_tasks:
        background_tasks.add_task(
            _process_pdf_bytes, paper_id, file_bytes, workspace_id
        )
    else:
        await _process_pdf_bytes(paper_id, file_bytes, workspace_id)

    paper_doc["_id"] = result.inserted_id
    paper_doc["storage_path"] = storage_path
    return serialize_doc(paper_doc)


async def batch_import(
    dois: List[str],
    workspace_id: str,
    user_id: str,
    background_tasks: BackgroundTasks = None,
) -> dict:
    """Batch import papers by DOI list."""
    results = {"imported": 0, "skipped": 0, "failed": 0, "papers": []}

    for doi in dois:
        try:
            # Search Crossref for metadata
            papers = await search_crossref(doi, limit=1)
            if papers:
                paper = await import_paper(
                    papers[0], workspace_id, user_id, background_tasks
                )
                results["imported"] += 1
                results["papers"].append(paper)
            else:
                results["failed"] += 1
        except Exception as e:
            print(f"Failed to import DOI {doi}: {e}")
            results["failed"] += 1

    return results


async def get_paper(paper_id: str) -> Optional[dict]:
    """Get a paper by ID."""
    db = get_db()
    try:
        paper = await db.papers.find_one({"_id": ObjectId(paper_id)})
        return serialize_doc(paper) if paper else None
    except Exception:
        return None


async def list_papers(workspace_id: str, skip: int = 0, limit: int = 50) -> List[dict]:
    """List papers in a workspace."""
    db = get_db()
    cursor = db.papers.find({"workspace_id": workspace_id}).sort("created_at", -1).skip(skip).limit(limit)
    papers = []
    async for doc in cursor:
        papers.append(serialize_doc(doc))
    return papers


async def delete_paper(paper_id: str, workspace_id: str) -> bool:
    """Delete a paper and its chunks/vectors."""
    db = get_db()

    paper = await db.papers.find_one({"_id": ObjectId(paper_id)})
    if not paper:
        return False

    # Delete vectors from Pinecone
    try:
        delete_by_paper(paper_id, namespace=workspace_id)
    except Exception as e:
        print(f"Pinecone delete failed: {e}")

    # Delete from Cloudinary
    if paper.get("storage_path"):
        try:
            delete_pdf(paper["storage_path"])
        except Exception as e:
            print(f"Cloudinary delete failed: {e}")

    # Delete chunks from MongoDB
    await db.chunks.delete_many({"paper_id": paper_id})

    # Delete paper
    await db.papers.delete_one({"_id": ObjectId(paper_id)})
    return True


async def get_paper_pdf_url(paper_id: str) -> Optional[str]:
    """Get signed PDF URL for a paper."""
    db = get_db()
    paper = await db.papers.find_one({"_id": ObjectId(paper_id)})
    if paper and paper.get("storage_path"):
        try:
            return get_pdf_url(paper["storage_path"])
        except Exception:
            pass
    return paper.get("pdf_url") if paper else None


# --- Background processing tasks ---

async def _process_paper_pdf(paper_id: str, pdf_url: str, workspace_id: str):
    """Download and process a paper's PDF."""
    db = get_db()
    try:
        await db.papers.update_one(
            {"_id": ObjectId(paper_id)},
            {"$set": {"status": PaperStatus.PROCESSING}},
        )

        # Download PDF
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(pdf_url)
            resp.raise_for_status()
            pdf_bytes = resp.content

        # Upload to Cloudinary
        try:
            storage_path = cloud_upload(pdf_bytes, paper_id)
            await db.papers.update_one(
                {"_id": ObjectId(paper_id)},
                {"$set": {"storage_path": storage_path}},
            )
        except Exception:
            pass

        # Process PDF
        await _process_pdf_bytes(paper_id, pdf_bytes, workspace_id)

    except Exception as e:
        print(f"Failed to process paper {paper_id}: {e}")
        await db.papers.update_one(
            {"_id": ObjectId(paper_id)},
            {"$set": {"status": PaperStatus.FAILED, "updated_at": utc_now()}},
        )


async def _try_fetch_and_process(paper_id: str, doi: str, workspace_id: str):
    """Try to find OA PDF via Unpaywall and process."""
    pdf_url = await fetch_unpaywall_pdf(doi)
    if pdf_url:
        await _process_paper_pdf(paper_id, pdf_url, workspace_id)


async def _process_pdf_bytes(paper_id: str, pdf_bytes: bytes, workspace_id: str):
    """Extract text, chunk, embed, and index a PDF."""
    db = get_db()
    try:
        # Extract text
        pages = extract_text_from_pdf(pdf_bytes)
        if not pages:
            await db.papers.update_one(
                {"_id": ObjectId(paper_id)},
                {"$set": {"status": PaperStatus.FAILED, "updated_at": utc_now()}},
            )
            return

        # Chunk text
        chunks = chunk_text(pages)
        if not chunks:
            await db.papers.update_one(
                {"_id": ObjectId(paper_id)},
                {"$set": {"status": PaperStatus.FAILED, "updated_at": utc_now()}},
            )
            return

        # Get paper title for metadata
        paper = await db.papers.find_one({"_id": ObjectId(paper_id)})
        paper_title = paper.get("title", "") if paper else ""

        # Store chunks in MongoDB
        chunk_docs = []
        chunk_texts = []
        for chunk in chunks:
            chunk_doc = {
                "paper_id": paper_id,
                "chunk_index": chunk.chunk_index,
                "text": chunk.text,
                "page_number": chunk.page_number,
                "char_start": chunk.char_start,
                "char_end": chunk.char_end,
                "checksum": chunk.checksum,
                "token_count": chunk.token_count,
                "created_at": utc_now(),
            }
            chunk_docs.append(chunk_doc)
            chunk_texts.append(chunk.text)

        result = await db.chunks.insert_many(chunk_docs)
        chunk_ids = [str(id) for id in result.inserted_ids]

        # Embed chunks
        embeddings = embed_batch(chunk_texts)

        # Prepare vectors for Pinecone
        vectors = []
        for i, (chunk_id, embedding) in enumerate(zip(chunk_ids, embeddings)):
            vectors.append({
                "id": chunk_id,
                "values": embedding,
                "metadata": {
                    "paper_id": paper_id,
                    "chunk_index": chunks[i].chunk_index,
                    "page_number": chunks[i].page_number or 0,
                    "text_preview": chunks[i].text[:200],
                    "paper_title": paper_title[:100],
                },
            })

        # Upsert to Pinecone
        upsert_chunks(vectors, namespace=workspace_id)

        # Update paper status
        await db.papers.update_one(
            {"_id": ObjectId(paper_id)},
            {
                "$set": {
                    "status": PaperStatus.INDEXED,
                    "chunk_count": len(chunks),
                    "updated_at": utc_now(),
                }
            },
        )

    except Exception as e:
        print(f"Failed to process PDF for paper {paper_id}: {e}")
        await db.papers.update_one(
            {"_id": ObjectId(paper_id)},
            {"$set": {"status": PaperStatus.FAILED, "updated_at": utc_now()}},
        )
