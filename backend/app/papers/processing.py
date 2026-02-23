"""PDF extraction, text chunking, and document processing."""

import fitz  # PyMuPDF
import hashlib
import re
from typing import List, Optional, Tuple
from app.papers.schemas import ChunkData

try:
    import tiktoken
    _enc = tiktoken.get_encoding("cl100k_base")
except Exception:
    _enc = None


def count_tokens(text: str) -> int:
    """Count tokens using tiktoken, fallback to word-based estimate."""
    if _enc:
        return len(_enc.encode(text))
    return len(text.split())


def extract_text_from_pdf(pdf_bytes: bytes) -> List[dict]:
    """
    Extract text from PDF bytes using PyMuPDF.
    Returns list of {page_number, text, char_start, char_end}.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    running_offset = 0

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        if text.strip():
            pages.append({
                "page_number": page_num + 1,
                "text": text,
                "char_start": running_offset,
                "char_end": running_offset + len(text),
            })
            running_offset += len(text)

    doc.close()
    return pages


def chunk_text(
    pages: List[dict],
    target_tokens: int = 1000,
    overlap_tokens: int = 200,
) -> List[ChunkData]:
    """
    Chunk extracted text into overlapping segments.
    target_tokens: target chunk size in tokens.
    overlap_tokens: number of overlapping tokens between chunks.
    """
    # Merge all page text
    full_text = ""
    page_boundaries = []  # (char_start, char_end, page_number)
    for p in pages:
        page_boundaries.append((len(full_text), len(full_text) + len(p["text"]), p["page_number"]))
        full_text += p["text"]

    if not full_text.strip():
        return []

    # Split into sentences for better chunk boundaries
    sentences = _split_sentences(full_text)

    chunks = []
    chunk_index = 0
    current_sentences = []
    current_tokens = 0
    char_pos = 0

    i = 0
    while i < len(sentences):
        sentence = sentences[i]
        sent_tokens = count_tokens(sentence)

        if current_tokens + sent_tokens <= target_tokens or not current_sentences:
            current_sentences.append(sentence)
            current_tokens += sent_tokens
            i += 1
        else:
            # Flush current chunk
            chunk_text_str = " ".join(current_sentences)
            char_start = full_text.find(current_sentences[0], char_pos)
            if char_start == -1:
                char_start = char_pos
            char_end = char_start + len(chunk_text_str)

            page_num = _find_page(char_start, page_boundaries)

            chunks.append(ChunkData(
                chunk_index=chunk_index,
                text=chunk_text_str,
                page_number=page_num,
                char_start=char_start,
                char_end=char_end,
                checksum=hashlib.md5(chunk_text_str.encode()).hexdigest(),
                token_count=current_tokens,
            ))
            chunk_index += 1

            # Calculate overlap: keep last N tokens worth of sentences
            overlap_sents = []
            overlap_count = 0
            for s in reversed(current_sentences):
                st = count_tokens(s)
                if overlap_count + st > overlap_tokens:
                    break
                overlap_sents.insert(0, s)
                overlap_count += st

            current_sentences = overlap_sents
            current_tokens = overlap_count
            char_pos = char_start + len(chunk_text_str) - len(" ".join(overlap_sents))

    # Flush remaining
    if current_sentences:
        chunk_text_str = " ".join(current_sentences)
        char_start = full_text.find(current_sentences[0], max(0, char_pos))
        if char_start == -1:
            char_start = max(0, len(full_text) - len(chunk_text_str))
        char_end = char_start + len(chunk_text_str)
        page_num = _find_page(char_start, page_boundaries)

        chunks.append(ChunkData(
            chunk_index=chunk_index,
            text=chunk_text_str,
            page_number=page_num,
            char_start=char_start,
            char_end=char_end,
            checksum=hashlib.md5(chunk_text_str.encode()).hexdigest(),
            token_count=current_tokens,
        ))

    return chunks


def detect_code_blocks(text: str) -> List[dict]:
    """Detect code blocks (LaTeX, pseudocode, Python, etc.) in text."""
    code_patterns = [
        (r"\\begin\{(algorithm|lstlisting|verbatim|minted)\}(.*?)\\end\{\1\}", "latex"),
        (r"```(\w*)\n(.*?)```", "markdown_code"),
        (r"(def |class |import |from .+ import |for .+ in |if __name__)", "python"),
    ]

    blocks = []
    for pattern, lang in code_patterns:
        for match in re.finditer(pattern, text, re.DOTALL):
            blocks.append({
                "language": lang,
                "code": match.group(0),
                "start": match.start(),
                "end": match.end(),
            })
    return blocks


def detect_tables(pdf_bytes: bytes) -> List[dict]:
    """Detect and extract tables from PDF. Returns list of table data."""
    tables = []
    try:
        import pdfplumber
        import io
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page_num, page in enumerate(pdf.pages):
                page_tables = page.extract_tables()
                for table_idx, table in enumerate(page_tables):
                    if table:
                        tables.append({
                            "page_number": page_num + 1,
                            "table_index": table_idx,
                            "data": table,
                            "headers": table[0] if table else [],
                            "rows": table[1:] if len(table) > 1 else [],
                        })
    except Exception:
        pass
    return tables


def _split_sentences(text: str) -> List[str]:
    """Split text into sentences."""
    # Simple sentence splitting by common delimiters
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]


def _find_page(char_offset: int, page_boundaries: List[Tuple]) -> Optional[int]:
    """Find which page a character offset belongs to."""
    for start, end, page_num in page_boundaries:
        if start <= char_offset < end:
            return page_num
    return page_boundaries[-1][2] if page_boundaries else None
