from __future__ import annotations

import hashlib
import os
import re
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Union

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

Block = Union[Paragraph, Table]

# Keep unique open copies briefly so python-docx never shares one package path.
_CACHE_TTL_SECONDS = 3600


def _cache_dir() -> Path:
    path = Path(tempfile.gettempdir()) / "document_ai_cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _cleanup_stale_copies(cache_dir: Path, *, ttl_seconds: int = _CACHE_TTL_SECONDS) -> None:
    """Best-effort cleanup of unique load copies (ignore locked files)."""
    now = time.time()
    for item in cache_dir.glob("open_*"):
        try:
            if now - item.stat().st_mtime > ttl_seconds:
                item.unlink(missing_ok=True)
        except OSError:
            continue


def _local_copy(path: Path) -> Path:
    """Copy DOCX to a *unique* temp file for each open.

    A shared cache path is unsafe with python-docx: Document keeps the package
    open, and reusing the same path across fills/tests yields non-deterministic
    XXCS renders on Windows (and can interact badly with force_generate).
    """
    path = Path(path).resolve()
    cache_dir = _cache_dir()
    _cleanup_stale_copies(cache_dir)
    path_key = hashlib.sha256(str(path).encode()).hexdigest()[:12]
    fd, tmp_name = tempfile.mkstemp(
        prefix=f"open_{path.stem}_{path_key}_",
        suffix=path.suffix,
        dir=cache_dir,
    )
    os.close(fd)
    tmp = Path(tmp_name)
    shutil.copy2(path, tmp)
    return tmp


def load_document(path: str | Path) -> Document:
    local = _local_copy(Path(path))
    return Document(str(local))


def iter_blocks(doc: Document) -> Iterator[Block]:
    for child in doc.element.body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, doc)
        elif child.tag == qn("w:tbl"):
            yield Table(child, doc)


def table_matrix(table: Table) -> list[list[str]]:
    return [[cell.text.strip() for cell in row.cells] for row in table.rows]


def paragraph_deep_text(paragraph: Paragraph) -> str:
    """Read paragraph text including SDT/content-control runs."""
    text = (paragraph.text or "").strip()
    if text:
        return text
    parts = re.findall(r"<w:t[^>]*>([^<]*)</w:t>", paragraph._p.xml)
    return "".join(parts).strip()


def set_paragraph_text(paragraph: Paragraph, text: str) -> None:
    paragraph.text = text


def block_snapshot(doc: Document) -> list[dict]:
    """Ordered list of paragraph texts and table matrices."""
    items: list[dict] = []
    for block in iter_blocks(doc):
        if isinstance(block, Paragraph):
            text = block.text.strip()
            if text:
                items.append({"kind": "paragraph", "text": text})
        elif isinstance(block, Table):
            items.append({"kind": "table", "matrix": table_matrix(block)})
    return items


@dataclass
class CellLocation:
    table_index: int
    row: int
    col: int
    label: str | None = None
