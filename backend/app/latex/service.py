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


async def compile_latex(source: str, timeout: int = 60) -> dict:
    """Compile LaTeX source to PDF using tectonic (primary) or pdflatex (fallback).

    Returns dict with pdf_base64 on success, or errors on failure.
    """
    import base64

    # Auto-wrap bare LaTeX in a document template if needed
    if "\\documentclass" not in source:
        source = f"""\\documentclass{{article}}
\\usepackage{{amsmath, amssymb, booktabs, graphicx, hyperref}}
\\usepackage[margin=1in]{{geometry}}
\\begin{{document}}
{source}
\\end{{document}}
"""

    # Find a LaTeX engine: prefer tectonic, fall back to pdflatex
    engine = None
    engine_type = None

    # Check tectonic first (brew install, no sudo needed)
    tectonic_bin = shutil.which("tectonic")
    if not tectonic_bin:
        for candidate in ["/opt/homebrew/bin/tectonic", "/usr/local/bin/tectonic"]:
            if os.path.isfile(candidate):
                tectonic_bin = candidate
                break
    if tectonic_bin:
        engine = tectonic_bin
        engine_type = "tectonic"

    # Fall back to pdflatex
    if not engine:
        pdflatex_bin = shutil.which("pdflatex")
        if not pdflatex_bin:
            for candidate in [
                "/Library/TeX/texbin/pdflatex",
                "/usr/local/texlive/2025/bin/universal-darwin/pdflatex",
                "/usr/local/texlive/2024/bin/universal-darwin/pdflatex",
                "/opt/homebrew/bin/pdflatex",
            ]:
                if os.path.isfile(candidate):
                    pdflatex_bin = candidate
                    break
        if pdflatex_bin:
            engine = pdflatex_bin
            engine_type = "pdflatex"

    if not engine:
        return {
            "success": False,
            "errors": [
                "No LaTeX engine found. Install tectonic: brew install tectonic"
            ],
            "log": "",
        }

    tmpdir = tempfile.mkdtemp(prefix="researchhub_latex_")
    tex_path = os.path.join(tmpdir, "document.tex")
    pdf_path = os.path.join(tmpdir, "document.pdf")
    log_path = os.path.join(tmpdir, "document.log")

    try:
        # Write source to temp file
        with open(tex_path, "w") as f:
            f.write(source)

        if engine_type == "tectonic":
            # Tectonic: single command, auto-downloads packages, produces PDF
            proc = await asyncio.create_subprocess_exec(
                engine,
                "--outdir", tmpdir,
                "--outfmt", "pdf",
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

            if proc.returncode != 0:
                output = (stderr or stdout or b"").decode("utf-8", errors="replace")
                errors = [line.strip() for line in output.split("\n")
                          if line.strip() and ("error" in line.lower() or line.startswith("!"))]
                if not errors:
                    errors = [output[-1000:] if len(output) > 1000 else output]
                return {
                    "success": False,
                    "errors": errors[:10],
                    "log": output[-2000:],
                }
        else:
            # pdflatex: run twice for references/toc
            for pass_num in range(2):
                proc = await asyncio.create_subprocess_exec(
                    engine,
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
                    log_content = ""
                    if os.path.exists(log_path):
                        with open(log_path, "r", errors="replace") as f:
                            log_content = f.read()
                    errors = [line.strip() for line in log_content.split("\n")
                              if line.startswith("!") or "Error" in line]
                    if not errors:
                        errors = ["Compilation failed (exit code {})".format(proc.returncode)]
                    return {
                        "success": False,
                        "errors": errors[:10],
                        "log": log_content[-2000:],
                    }

        # Read PDF
        if os.path.exists(pdf_path):
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
            "errors": ["LaTeX engine not found. Install tectonic: brew install tectonic"],
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
        shutil.rmtree(tmpdir, ignore_errors=True)

