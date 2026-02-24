"""Supabase Storage client for PDF file management."""

import httpx
from app.config import settings

BUCKET_NAME = "papers"


def _headers():
    """Build authorization headers for Supabase Storage API."""
    return {
        "apikey": settings.SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_ANON_KEY}",
    }


def _storage_url(path: str = "") -> str:
    """Build Supabase Storage REST URL."""
    base = f"{settings.SUPABASE_URL}/storage/v1"
    return f"{base}/{path}" if path else base


async def ensure_storage():
    """Ensure the papers bucket exists."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        # List existing buckets
        resp = await client.get(_storage_url("bucket"), headers=_headers())
        if resp.status_code == 200:
            buckets = resp.json()
            if any(b["id"] == BUCKET_NAME for b in buckets):
                return True

        # Create the bucket
        resp = await client.post(
            _storage_url("bucket"),
            headers={**_headers(), "Content-Type": "application/json"},
            json={
                "id": BUCKET_NAME,
                "name": BUCKET_NAME,
                "public": True,
                "file_size_limit": 52428800,  # 50MB
            },
        )
        return resp.status_code in (200, 201)


async def upload_pdf(
    file_bytes: bytes,
    paper_id: str,
    filename: str = None,
) -> dict:
    """Upload a PDF to Supabase Storage. Returns dict with path and url."""
    filename = filename or f"{paper_id}.pdf"
    object_path = f"{paper_id}/{filename}"

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            _storage_url(f"object/{BUCKET_NAME}/{object_path}"),
            headers={
                **_headers(),
                "Content-Type": "application/pdf",
                "x-upsert": "true",
            },
            content=file_bytes,
        )
        resp.raise_for_status()

    public_url = f"{settings.SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{object_path}"
    return {
        "path": object_path,
        "url": public_url,
        "bucket": BUCKET_NAME,
    }


def get_public_url(paper_id: str, filename: str = None) -> str:
    """Get the public URL for a stored PDF."""
    filename = filename or f"{paper_id}.pdf"
    object_path = f"{paper_id}/{filename}"
    return f"{settings.SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{object_path}"


async def download_pdf(paper_id: str, filename: str = None) -> bytes:
    """Download a PDF from Supabase Storage."""
    filename = filename or f"{paper_id}.pdf"
    object_path = f"{paper_id}/{filename}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            _storage_url(f"object/{BUCKET_NAME}/{object_path}"),
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.content


async def delete_pdf(paper_id: str, filename: str = None) -> bool:
    """Delete a PDF from Supabase Storage."""
    filename = filename or f"{paper_id}.pdf"
    object_path = f"{paper_id}/{filename}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.delete(
            _storage_url(f"object/{BUCKET_NAME}"),
            headers={**_headers(), "Content-Type": "application/json"},
            json={"prefixes": [object_path]},
        )
        return resp.status_code in (200, 204)
