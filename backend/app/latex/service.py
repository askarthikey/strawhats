"""LaTeX generation and compilation service."""

import asyncio
import os
import tempfile
import shutil
import logging

from app.llm.provider import get_llm_provider

logger = logging.getLogger(__name__)

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


async def compile_latex(source: str, timeout: int = 30) -> dict:
    """Compile LaTeX source to PDF using pdflatex.

    Returns dict with pdf_base64 on success, or errors on failure.
    """
    tmpdir = tempfile.mkdtemp(prefix="researchhub_latex_")
    tex_path = os.path.join(tmpdir, "document.tex")
    pdf_path = os.path.join(tmpdir, "document.pdf")
    log_path = os.path.join(tmpdir, "document.log")

    try:
        # Write source to temp file
        with open(tex_path, "w") as f:
            f.write(source)

        # Run pdflatex twice (for references/toc)
        for pass_num in range(2):
            proc = await asyncio.create_subprocess_exec(
                "pdflatex",
                "-interaction=nonstopmode",
                "-halt-on-error",
                "-output-directory", tmpdir,
                tex_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                return {
                    "success": False,
                    "errors": ["Compilation timed out after {} seconds".format(timeout)],
                    "log": "",
                }

            if proc.returncode != 0 and pass_num == 0:
                # Read log for error details
                log_content = ""
                if os.path.exists(log_path):
                    with open(log_path, "r", errors="replace") as f:
                        log_content = f.read()

                # Extract error lines
                errors = []
                for line in log_content.split("\n"):
                    if line.startswith("!") or "Error" in line:
                        errors.append(line.strip())

                if not errors:
                    errors = ["Compilation failed (exit code {})".format(proc.returncode)]

                return {
                    "success": False,
                    "errors": errors[:10],  # Limit error count
                    "log": log_content[-2000:],  # Last 2000 chars of log
                }

        # Read PDF
        if os.path.exists(pdf_path):
            import base64
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()

            return {
                "success": True,
                "pdf_base64": base64.b64encode(pdf_bytes).decode("ascii"),
                "pdf_size": len(pdf_bytes),
            }
        else:
            return {
                "success": False,
                "errors": ["PDF not generated despite successful compilation"],
                "log": "",
            }

    except FileNotFoundError:
        return {
            "success": False,
            "errors": [
                "pdflatex not found. Install texlive: sudo apt-get install texlive-latex-base texlive-latex-extra texlive-fonts-recommended"
            ],
            "log": "",
        }
    except Exception as e:
        logger.error(f"LaTeX compilation error: {e}")
        return {
            "success": False,
            "errors": [str(e)],
            "log": "",
        }
    finally:
        # Cleanup temp directory
        shutil.rmtree(tmpdir, ignore_errors=True)
