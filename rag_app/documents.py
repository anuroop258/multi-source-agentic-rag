from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import hashlib
import re

@dataclass
class TextChunk:
    chunk_id: str
    text: str
    metadata: dict

def _extract_pdf(path: Path) -> list[tuple[str, int | None]]:
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    return [(page.extract_text() or "", i + 1) for i, page in enumerate(reader.pages)]

def _extract_docx(path: Path) -> list[tuple[str, int | None]]:
    from docx import Document
    doc = Document(str(path))
    return [("\n".join(p.text for p in doc.paragraphs), None)]

def extract_document(path: Path) -> list[tuple[str, int | None]]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf(path)
    if suffix == ".docx":
        return _extract_docx(path)
    if suffix in {".txt", ".md", ".markdown", ".csv"}:
        return [(path.read_text(encoding="utf-8", errors="replace"), None)]
    raise ValueError(f"Unsupported file type: {suffix}. Supported: PDF, DOCX, TXT, MD, CSV.")

def _split_text(text: str, chunk_size: int = 1100, overlap: int = 160) -> list[str]:
    """Paragraph-aware character splitter; deterministic and dependency-light."""
    text = re.sub(r"\r\n?", "\n", text).strip()
    if not text:
        return []
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        while len(paragraph) > chunk_size:
            head = paragraph[:chunk_size]
            split_at = max(head.rfind(". "), head.rfind("\n"), head.rfind(" "))
            if split_at < int(chunk_size * 0.55):
                split_at = chunk_size
            piece = paragraph[:split_at].strip()
            if piece:
                if current:
                    chunks.append(current)
                    current = ""
                chunks.append(piece)
            paragraph = paragraph[max(0, split_at - overlap):].strip()
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                chunks.append(current)
            tail = current[-overlap:] if current else ""
            current = f"{tail}\n{paragraph}".strip() if tail else paragraph
    if current:
        chunks.append(current)
    # Keep overlap only when a previous chunk exists and avoid empty/duplicate chunks.
    cleaned = []
    for chunk in chunks:
        chunk = chunk.strip()
        if chunk and (not cleaned or chunk != cleaned[-1]):
            cleaned.append(chunk)
    return cleaned

def load_and_chunk(paths: Iterable[Path], chunk_size: int = 1100, overlap: int = 160) -> list[TextChunk]:
    output: list[TextChunk] = []
    for path in paths:
        source = path.name
        page_items = extract_document(path)
        for page_text, page_number in page_items:
            for index, chunk in enumerate(_split_text(page_text, chunk_size, overlap)):
                digest = hashlib.sha256(f"{source}|{page_number}|{index}|{chunk}".encode("utf-8")).hexdigest()
                output.append(TextChunk(
                    chunk_id=digest,
                    text=chunk,
                    metadata={
                        "source": source,
                        "page": int(page_number) if page_number is not None else 0,
                        "chunk_index": int(index),
                    },
                ))
    return output
