"""LLM provider factory with automatic fallback."""

from typing import AsyncGenerator
from app.llm import ollama_client, gemini_client


class LLMProvider:
    """Unified LLM provider interface."""

    def __init__(self, name: str):
        self.name = name

    async def generate_stream(
        self, prompt: str, system_prompt: str = "", temperature: float = 0.0, max_tokens: int = 4096
    ) -> AsyncGenerator[str, None]:
        raise NotImplementedError

    async def generate(
        self, prompt: str, system_prompt: str = "", temperature: float = 0.0, max_tokens: int = 4096
    ) -> str:
        raise NotImplementedError

    async def check_health(self) -> bool:
        raise NotImplementedError


class OllamaProvider(LLMProvider):
    def __init__(self):
        super().__init__("ollama")

    async def generate_stream(self, prompt, system_prompt="", temperature=0.0, max_tokens=4096):
        async for token in ollama_client.generate_stream(prompt, system_prompt, temperature=temperature, max_tokens=max_tokens):
            yield token

    async def generate(self, prompt, system_prompt="", temperature=0.0, max_tokens=4096):
        return await ollama_client.generate(prompt, system_prompt, temperature=temperature, max_tokens=max_tokens)

    async def check_health(self):
        return await ollama_client.check_health()


class GeminiProvider(LLMProvider):
    def __init__(self):
        super().__init__("gemini")

    async def generate_stream(self, prompt, system_prompt="", temperature=0.0, max_tokens=4096):
        async for token in gemini_client.generate_stream(prompt, system_prompt, temperature=temperature, max_tokens=max_tokens):
            yield token

    async def generate(self, prompt, system_prompt="", temperature=0.0, max_tokens=4096):
        return await gemini_client.generate(prompt, system_prompt, temperature=temperature, max_tokens=max_tokens)

    async def check_health(self):
        return await gemini_client.check_health()


async def get_llm_provider(preference: str = "gemini") -> LLMProvider:
    """
    Get LLM provider with fallback.
    Default: Gemini first, Ollama fallback.
    """
    if preference == "ollama":
        ollama = OllamaProvider()
        if await ollama.check_health():
            return ollama
        # Fall back to Gemini if Ollama is unavailable
        gemini = GeminiProvider()
        if await gemini.check_health():
            return gemini
        return ollama  # Return anyway, will error on use

    # Default: try Gemini first
    gemini = GeminiProvider()
    if await gemini.check_health():
        return gemini

    # Fallback to Ollama
    ollama = OllamaProvider()
    if await ollama.check_health():
        return ollama

    return gemini  # Return anyway, will error on use
