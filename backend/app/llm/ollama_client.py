"""Ollama client for local Llama 3.2 inference."""

import httpx
from typing import AsyncGenerator, Optional
from app.config import settings


async def check_health() -> bool:
    """Check if Ollama is running and accessible."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            return resp.status_code == 200
    except Exception:
        return False


async def check_model(model: str = "llama3.2") -> bool:
    """Check if a specific model is available."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                return any(m["name"].startswith(model) for m in models)
    except Exception:
        pass
    return False


async def generate_stream(
    prompt: str,
    system_prompt: str = "",
    model: str = "llama3.2",
    temperature: float = 0.0,
    max_tokens: int = 4096,
) -> AsyncGenerator[str, None]:
    """Stream tokens from Ollama. Yields individual token strings."""
    payload = {
        "model": model,
        "prompt": prompt,
        "system": system_prompt,
        "stream": True,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            f"{settings.OLLAMA_BASE_URL}/api/generate",
            json=payload,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.strip():
                    import ujson
                    try:
                        data = ujson.loads(line)
                        token = data.get("response", "")
                        if token:
                            yield token
                        if data.get("done", False):
                            return
                    except Exception:
                        continue


async def generate(
    prompt: str,
    system_prompt: str = "",
    model: str = "llama3.2",
    temperature: float = 0.0,
    max_tokens: int = 4096,
) -> str:
    """Generate a complete response from Ollama."""
    full_response = ""
    async for token in generate_stream(prompt, system_prompt, model, temperature, max_tokens):
        full_response += token
    return full_response
