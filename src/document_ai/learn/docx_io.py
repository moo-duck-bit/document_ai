from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Union

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

Block = Union[Paragraph, Table]


def _local_copy(path: Path) -> Path:
    """Copy cloud-backed DOCX to temp so python-docx reads reliably."""
    path = Path(path).resolve()
    cache_dir = Path(tempfile.gettempdir()) / "document_ai_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    path_key = hashlib.sha256(str(path).encode()).hexdigest()[:16]
    tmp = cache_dir / f"{path.stem}_{path_key}{path.suffix}"
    refresh = os.environ.get("DOCUMENT_AI_REFRESH_CACHE", "").lower() in {"1", "true", "yes"}
    src_mtime = path.stat().st_mtime if path.exists() else 0.0
    cache_stale = not tmp.exists() or src_mtime > tmp.stat().st_mtime
    if refresh or cache_stale:
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


def block_snapshot(doc: Document) -> list[dict]:
    """Ordered list of paragraph texts and table matrices."""
    from pathlib import Path

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
