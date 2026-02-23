"""LaTeX generation service."""

from app.llm.provider import get_llm_provider

LATEX_SYSTEM_PROMPT = """You are a LaTeX expert. Generate clean, compilable LaTeX code based on the user's request.
Rules:
1. Output ONLY valid LaTeX code, no explanations unless asked.
2. Use standard packages (amsmath, amssymb, algorithm2e, booktabs, graphicx).
3. Wrap the output in appropriate LaTeX environments.
4. For equations: use align, equation, or gather environments.
5. For tables: use tabular with booktabs formatting.
6. For algorithms: use algorithm2e package.
7. Ensure the code compiles without errors.
"""

LATEX_TYPES = {
    "equation": "Generate a LaTeX equation for: {prompt}",
    "table": "Generate a LaTeX table for: {prompt}",
    "algorithm": "Generate a LaTeX algorithm pseudocode for: {prompt}",
    "figure": "Generate a LaTeX figure environment for: {prompt}",
    "general": "{prompt}",
}


async def generate_latex(
    prompt: str,
    latex_type: str = "general",
    provider_name: str = "ollama",
) -> dict:
    """Generate LaTeX code using LLM."""
    template = LATEX_TYPES.get(latex_type, LATEX_TYPES["general"])
    formatted_prompt = template.format(prompt=prompt)

    provider = await get_llm_provider(provider_name)
    result = await provider.generate(
        prompt=formatted_prompt,
        system_prompt=LATEX_SYSTEM_PROMPT,
        temperature=0.1,
    )

    return {
        "latex": result,
        "type": latex_type,
        "provider": provider.name,
    }
