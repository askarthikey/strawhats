"""Google Gemini API client for LLM inference."""

import asyncio
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
    """Check if Gemini API is accessible (without wasting quota)."""
    try:
        _ensure_configured()
        return bool(settings.GEMINI_API_KEY)
    except Exception:
        return False


async def generate_stream(
    prompt: str,
    system_prompt: str = "",
    model_name: str = "gemini-2.5-flash",
    temperature: float = 0.0,
    max_tokens: int = 4096,
) -> AsyncGenerator[str, None]:
    """Stream tokens from Gemini. Yields individual token strings."""
    _ensure_configured()

    generation_config = {
        "temperature": temperature,
        "max_output_tokens": max_tokens,
    }

    # Try models in order of preference
    models_to_try = [model_name, "gemini-2.5-flash"]
    last_error = None

    for try_model in models_to_try:
        try:
            model = genai.GenerativeModel(
                try_model,
                system_instruction=system_prompt if system_prompt else None,
            )

            # Retry with backoff for rate limiting
            for attempt in range(3):
                try:
                    response = model.generate_content(
                        prompt,
                        generation_config=generation_config,
                        stream=True,
                    )

                    for chunk in response:
                        if chunk.text:
                            yield chunk.text
                    return  # Success
                except Exception as e:
                    error_msg = str(e)
                    if "429" in error_msg or "quota" in error_msg.lower() or "rate" in error_msg.lower():
                        wait_time = (2 ** attempt) * 2  # 2, 4, 8 seconds
                        await asyncio.sleep(wait_time)
                        last_error = e
                        continue
                    raise  # Non-rate-limit error
        except Exception as e:
            last_error = e
            continue

    if last_error:
        raise last_error


async def generate(
    prompt: str,
    system_prompt: str = "",
    model_name: str = "gemini-2.5-flash",
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
