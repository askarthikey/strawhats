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
from app.utils.vector_store import upsert_chunks, delete_by_paper
from app.utils.helpers import utc_now, generate_dedup_hash, serialize_doc
from app.storage.unified import upload_pdf as storage_upload, get_pdf_url, delete_pdf as storage_delete
from app.papers.status_ws import notify_paper_status
import httpx

MAX_PDF_SIZE = 50 * 1024 * 1024  # 50 MB


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

    # Create paper document (omit doi when None so sparse unique index allows multiple nulls)
    paper_doc = {
        "title": metadata.title,
        "authors": metadata.authors,
        "year": metadata.year,
        "venue": metadata.venue,
        "abstract": metadata.abstract,
        "pdf_url": metadata.pdf_url,
        "license": metadata.license,
        "source": metadata.source,
        "workspace_id": workspace_id,
        "added_by": user_id,
        "status": PaperStatus.PENDING,
        "status_reason": None,
        "storage_path": None,
        "chunk_count": 0,
        "dedup_hash": dedup_hash,
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    if metadata.doi:
        paper_doc["doi"] = metadata.doi
    try:
        result = await db.papers.insert_one(paper_doc)
    except Exception as e:
        # Handle DuplicateKeyError (e.g. same DOI in same workspace race condition)
        if "DuplicateKeyError" in str(type(e).__name__) or "E11000" in str(e):
            existing = await db.papers.find_one({
                "doi": metadata.doi,
                "workspace_id": workspace_id,
            })
            if existing:
                return serialize_doc(existing)
        raise
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
    import uuid
    db = get_db()

    file_bytes = await file.read()
    filename = file.filename or "upload.pdf"

    # Generate a unique DOI-like identifier for uploaded PDFs
    # (MongoDB sparse unique index on doi+workspace_id treats null as a value)
    upload_doi = f"upload:{uuid.uuid4().hex[:16]}"

    paper_doc = {
        "title": title or filename.replace(".pdf", ""),
        "doi": upload_doi,
        "authors": [],
        "year": None,
        "venue": None,
        "abstract": None,
        "pdf_url": None,
        "source": "upload",
        "workspace_id": workspace_id,
        "added_by": user_id,
        "status": PaperStatus.PROCESSING,
        "status_reason": None,
        "storage_path": None,
        "chunk_count": 0,
        "dedup_hash": None,
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    result = await db.papers.insert_one(paper_doc)
    paper_id = str(result.inserted_id)

    # Upload to storage
    try:
        storage_result = await storage_upload(file_bytes, paper_id, filename)
        await db.papers.update_one(
            {"_id": result.inserted_id},
            {"$set": {
                "storage_path": storage_result["path"],
                "storage_url": storage_result["url"],
                "storage_provider": storage_result["provider"],
            }},
        )
    except Exception as e:
        print(f"Storage upload failed: {e}")
        storage_result = None

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

async def _download_pdf(pdf_url: str) -> bytes:
    """Download PDF with browser-like headers. Raises on failure."""
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/pdf,*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": pdf_url,
    }
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        resp = await client.get(pdf_url, headers=headers)
        if resp.status_code == 403:
            raise ValueError("PDF not downloadable — access forbidden (HTTP 403)")
        if resp.status_code == 404:
            raise ValueError("PDF not found — the URL may have changed (HTTP 404)")
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "html" in content_type and "pdf" not in content_type:
            raise ValueError("PDF behind publisher paywall — received HTML instead of PDF")
        if len(resp.content) > MAX_PDF_SIZE:
            size_mb = len(resp.content) / (1024 * 1024)
            raise ValueError(f"PDF too large ({size_mb:.1f} MB) — maximum is 50 MB")
        if len(resp.content) < 100:
            raise ValueError("Invalid PDF — file is too small to be a valid document")
        return resp.content


async def _process_paper_pdf(paper_id: str, pdf_url: str, workspace_id: str):
    """Download and process a paper's PDF."""
    db = get_db()
    try:
        await db.papers.update_one(
            {"_id": ObjectId(paper_id)},
            {"$set": {"status": PaperStatus.PROCESSING}},
        )
        paper = await db.papers.find_one({"_id": ObjectId(paper_id)})
        paper_title = paper.get("title", "") if paper else ""
        paper_doi = paper.get("doi") if paper else None
        await notify_paper_status(workspace_id, paper_id, "processing", "Downloading PDF...", title=paper_title)

        # Try direct download first, then Unpaywall fallback
        pdf_bytes = None
        download_reason = None
        try:
            pdf_bytes = await _download_pdf(pdf_url)
        except (httpx.HTTPStatusError, ValueError) as dl_err:
            download_reason = str(dl_err)
            print(f"Direct PDF download failed for {paper_id}: {dl_err}")
            # Fallback: try Unpaywall for an open-access PDF
            if paper_doi:
                print(f"Trying Unpaywall fallback for DOI {paper_doi}...")
                alt_url = await fetch_unpaywall_pdf(paper_doi)
                if alt_url and alt_url != pdf_url:
                    try:
                        pdf_bytes = await _download_pdf(alt_url)
                        download_reason = None  # fallback succeeded
                        print(f"Unpaywall fallback succeeded for {paper_id}")
                    except Exception as alt_err:
                        download_reason = str(alt_err)
                        print(f"Unpaywall fallback also failed: {alt_err}")
        except httpx.TimeoutException:
            download_reason = "PDF download timed out — server did not respond in 60 seconds"

        if pdf_bytes is None:
            # Could not obtain PDF — keep as metadata-only with a specific reason
            if not download_reason:
                download_reason = "PDF not accessible — no open-access version found"
            print(f"PDF unavailable for paper {paper_id}: {download_reason}")
            await db.papers.update_one(
                {"_id": ObjectId(paper_id)},
                {"$set": {
                    "status": PaperStatus.PENDING,
                    "status_reason": download_reason,
                    "updated_at": utc_now(),
                }},
            )
            await notify_paper_status(
                workspace_id, paper_id, "pending",
                download_reason,
                title=paper_title,
            )
            return

        # Upload to storage
        try:
            storage_result = await storage_upload(pdf_bytes, paper_id)
            await db.papers.update_one(
                {"_id": ObjectId(paper_id)},
                {"$set": {
                    "storage_path": storage_result["path"],
                    "storage_url": storage_result["url"],
                    "storage_provider": storage_result["provider"],
                }},
            )
        except Exception:
            pass

        # Process PDF
        await _process_pdf_bytes(paper_id, pdf_bytes, workspace_id)

    except Exception as e:
        reason = str(e)
        print(f"Failed to process paper {paper_id}: {reason}")
        await db.papers.update_one(
            {"_id": ObjectId(paper_id)},
            {"$set": {
                "status": PaperStatus.FAILED,
                "status_reason": reason,
                "updated_at": utc_now(),
            }},
        )
        await notify_paper_status(workspace_id, paper_id, "failed", reason)


async def _try_fetch_and_process(paper_id: str, doi: str, workspace_id: str):
    """Try to find OA PDF via Unpaywall and process."""
    pdf_url = await fetch_unpaywall_pdf(doi)
    if pdf_url:
        await _process_paper_pdf(paper_id, pdf_url, workspace_id)
    else:
        # No open-access PDF found — update status with reason
        db = get_db()
        reason = "No open-access PDF available for this DOI"
        await db.papers.update_one(
            {"_id": ObjectId(paper_id)},
            {"$set": {
                "status": PaperStatus.PENDING,
                "status_reason": reason,
                "updated_at": utc_now(),
            }},
        )
        paper = await db.papers.find_one({"_id": ObjectId(paper_id)})
        paper_title = paper.get("title", "") if paper else ""
        await notify_paper_status(workspace_id, paper_id, "pending", reason, title=paper_title)


async def _process_pdf_bytes(paper_id: str, pdf_bytes: bytes, workspace_id: str):
    """Extract text, chunk, embed, and index a PDF."""
    db = get_db()
    try:
        # Get paper title for status messages
        paper = await db.papers.find_one({"_id": ObjectId(paper_id)})
        paper_title = paper.get("title", "") if paper else ""

        await notify_paper_status(workspace_id, paper_id, "processing", "Extracting text from PDF...", title=paper_title)

        # Extract text
        pages = extract_text_from_pdf(pdf_bytes)
        if not pages:
            await db.papers.update_one(
                {"_id": ObjectId(paper_id)},
                {"$set": {"status": PaperStatus.FAILED, "updated_at": utc_now()}},
            )
            await notify_paper_status(workspace_id, paper_id, "failed", "Could not extract text from PDF", title=paper_title)
            return

        await notify_paper_status(workspace_id, paper_id, "processing", f"Chunking {len(pages)} pages...", title=paper_title)

        # Chunk text
        chunks = chunk_text(pages)
        if not chunks:
            await db.papers.update_one(
                {"_id": ObjectId(paper_id)},
                {"$set": {"status": PaperStatus.FAILED, "updated_at": utc_now()}},
            )
            await notify_paper_status(workspace_id, paper_id, "failed", "No chunks produced", title=paper_title)
            return

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

        await notify_paper_status(workspace_id, paper_id, "processing", f"Embedding {len(chunks)} chunks...", title=paper_title)

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
        await notify_paper_status(workspace_id, paper_id, "processing", "Indexing in vector store...", title=paper_title)
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
        await notify_paper_status(workspace_id, paper_id, "indexed", "Processing complete", chunk_count=len(chunks), title=paper_title)

    except Exception as e:
        print(f"Failed to process PDF for paper {paper_id}: {e}")
        await db.papers.update_one(
            {"_id": ObjectId(paper_id)},
            {"$set": {"status": PaperStatus.FAILED, "updated_at": utc_now()}},
        )
        await notify_paper_status(workspace_id, paper_id, "failed", str(e))
