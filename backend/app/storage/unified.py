"""Unified storage layer: Supabase primary, Cloudinary backup."""

from typing import Optional
from app.storage import supabase_client, cloudinary_client


async def upload_pdf(file_bytes: bytes, paper_id: str, filename: Optional[str] = None) -> dict:
    """Upload PDF to Supabase (primary), fall back to Cloudinary.
    Returns dict with 'path', 'url', 'provider'.
    """
    safe_filename = filename or f"{paper_id}.pdf"
    # Try Supabase first
    try:
        result = await supabase_client.upload_pdf(file_bytes, paper_id, safe_filename)
        return {
            "path": result["path"],
            "url": result["url"],
            "provider": "supabase",
        }
    except Exception as e:
        print(f"Supabase upload failed, falling back to Cloudinary: {e}")

    # Fallback to Cloudinary
    storage_path = await cloudinary_client.upload_pdf(file_bytes, paper_id, safe_filename)
    url = cloudinary_client.get_pdf_url(storage_path)
    return {
        "path": storage_path,
        "url": url,
        "provider": "cloudinary",
    }


async def download_pdf(paper_doc: dict) -> bytes:
    """Download PDF using the provider stored in the paper document."""
    provider = paper_doc.get("storage_provider", "cloudinary")
    storage_path = paper_doc.get("storage_path", "")

    if provider == "supabase":
        paper_id = str(paper_doc.get("_id", paper_doc.get("id", "")))
        return await supabase_client.download_pdf(paper_id)
    else:
        return await cloudinary_client.download_pdf(storage_path)


async def delete_pdf(paper_doc: dict) -> bool:
    """Delete PDF using the provider stored in the paper document."""
    provider = paper_doc.get("storage_provider", "cloudinary")
    storage_path = paper_doc.get("storage_path", "")
    paper_id = str(paper_doc.get("_id", paper_doc.get("id", "")))

    try:
        if provider == "supabase":
            return await supabase_client.delete_pdf(paper_id)
        else:
            await cloudinary_client.delete_pdf(storage_path)
            return True
    except Exception as e:
        print(f"Failed to delete PDF ({provider}): {e}")
        return False


def get_pdf_url(paper_doc: dict) -> str:
    """Get the public URL for a stored PDF."""
    provider = paper_doc.get("storage_provider", "cloudinary")
    storage_path = paper_doc.get("storage_path", "")
    paper_id = str(paper_doc.get("_id", paper_doc.get("id", "")))

    if provider == "supabase":
        return supabase_client.get_public_url(paper_id)
    else:
        return cloudinary_client.get_pdf_url(storage_path)


async def ensure_storage():
    """Ensure both storage backends are available."""
    results = {}
    try:
        results["supabase"] = await supabase_client.ensure_storage()
    except Exception:
        results["supabase"] = False
    try:
        results["cloudinary"] = await cloudinary_client.ensure_storage()
    except Exception:
        results["cloudinary"] = False
    return results
