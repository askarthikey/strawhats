"""Google Gemini API client for LLM inference."""

from typing import AsyncGenerator
import google.generativeai as genai
from app.config import settings

_configured = False


def _ensure_configured():
    global _configured
    if not _configured and settings.GEMINI_API_KEY:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        _configured = True


async def check_health() -> bool:
    """Check if Gemini API is accessible."""
    try:
        _ensure_configured()
        if not settings.GEMINI_API_KEY:
            return False
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content("Hello", generation_config={"max_output_tokens": 5})
        return response.text is not None
    except Exception:
        return False


async def generate_stream(
    prompt: str,
    system_prompt: str = "",
    model_name: str = "gemini-2.0-flash",
    temperature: float = 0.0,
    max_tokens: int = 4096,
) -> AsyncGenerator[str, None]:
    """Stream tokens from Gemini. Yields individual token strings."""
    _ensure_configured()

    model = genai.GenerativeModel(
        model_name,
        system_instruction=system_prompt if system_prompt else None,
    )

    generation_config = {
        "temperature": temperature,
        "max_output_tokens": max_tokens,
    }

    response = model.generate_content(
        prompt,
        generation_config=generation_config,
        stream=True,
    )

    for chunk in response:
        if chunk.text:
            yield chunk.text


async def generate(
    prompt: str,
    system_prompt: str = "",
    model_name: str = "gemini-2.0-flash",
    temperature: float = 0.0,
    max_tokens: int = 4096,
) -> str:
    """Generate a complete response from Gemini."""
    _ensure_configured()

    model = genai.GenerativeModel(
        model_name,
        system_instruction=system_prompt if system_prompt else None,
    )

    generation_config = {
        "temperature": temperature,
        "max_output_tokens": max_tokens,
    }

    response = model.generate_content(
        prompt,
        generation_config=generation_config,
    )

    return response.text
