"""Cloudinary storage client for PDF file management."""

import io
import cloudinary
import cloudinary.uploader
import cloudinary.api
from app.config import settings

_configured = False
FOLDER_PREFIX = "researchhub/papers"


def _ensure_configured():
    """Configure Cloudinary SDK once."""
    global _configured
    if not _configured:
        cloudinary.config(
            cloud_name=settings.CLOUDINARY_CLOUD_NAME,
            api_key=settings.CLOUDINARY_API_KEY,
            api_secret=settings.CLOUDINARY_API_SECRET,
            secure=True,
        )
        _configured = True


def upload_pdf(file_bytes: bytes, paper_id: str, filename: str = None) -> str:
    """Upload a PDF to Cloudinary. Returns the public_id (storage path)."""
    _ensure_configured()
    public_id = f"{FOLDER_PREFIX}/{paper_id}/{filename or paper_id}"

    # Wrap bytes in BytesIO so Cloudinary SDK can read it as a file
    file_stream = io.BytesIO(file_bytes)

    result = cloudinary.uploader.upload(
        file_stream,
        public_id=public_id,
        resource_type="raw",
        overwrite=True,
    )
    return result.get("public_id", public_id)


def get_pdf_url(storage_path: str, expires_in: int = 3600) -> str:
    """Get a URL for a stored PDF. Cloudinary raw URLs are direct access."""
    _ensure_configured()
    try:
        result = cloudinary.api.resource(storage_path, resource_type="raw")
        return result.get("secure_url", "")
    except Exception:
        # Build URL directly
        return cloudinary.utils.cloudinary_url(
            storage_path, resource_type="raw", secure=True
        )[0]


def download_pdf(storage_path: str) -> bytes:
    """Download PDF bytes from Cloudinary."""
    _ensure_configured()
    import httpx
    url = get_pdf_url(storage_path)
    resp = httpx.get(url, timeout=60.0)
    resp.raise_for_status()
    return resp.content


def delete_pdf(storage_path: str):
    """Delete a PDF from Cloudinary."""
    _ensure_configured()
    cloudinary.uploader.destroy(storage_path, resource_type="raw")


def list_pdfs(paper_id: str) -> list:
    """List files for a given paper."""
    _ensure_configured()
    prefix = f"{FOLDER_PREFIX}/{paper_id}"
    try:
        result = cloudinary.api.resources(
            type="upload",
            resource_type="raw",
            prefix=prefix,
            max_results=100,
        )
        return result.get("resources", [])
    except Exception:
        return []


async def ensure_storage():
    """Verify Cloudinary connectivity. No bucket creation needed."""
    _ensure_configured()
    try:
        cloudinary.api.ping()
        return True
    except Exception as e:
        print(f"Cloudinary connectivity check failed: {e}")
        return False
