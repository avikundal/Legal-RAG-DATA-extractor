from __future__ import annotations

import re
from typing import Any, List, Optional

from .schemas import Chunk


DEFAULT_MAX_CHARS = 1800


def _clean_text(text: str) -> str:
    if not text:
        return ""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _clean_line(line: str) -> str:
    return re.sub(r"[ \t]+", " ", line).strip()


def _is_numbered_clause_start(line: str) -> bool:
    t = line.strip()
    if not t:
        return False

    # 7.NON-COMPETE...
    if re.match(r"^\d+\.[A-Z]", t):
        return True

    # 7. NON-COMPETE...
    if re.match(r"^\d+\.\s*[A-Z]", t):
        return True

    # 7.1 Something
    if re.match(r"^\d+(\.\d+)+\s*[A-Z]", t):
        return True

    return False


def _is_subclause_line(line: str) -> bool:
    t = line.strip()
    if not t:
        return False

    if re.match(r"^[a-zA-Z]\.\s+", t):
        return True

    if re.match(r"^\([a-zA-Z0-9]+\)\s+", t):
        return True

    return False


def _is_heading(line: str) -> bool:
    t = line.strip()
    if not t:
        return False

    if t.isupper() and 1 <= len(t.split()) <= 12:
        return True

    if re.match(r"^[A-Z][A-Z0-9 ,&/\-\(\)]+:$", t):
        return True

    return False


def _infer_section_hint(text: str) -> Optional[str]:
    lines = [_clean_line(x) for x in text.split("\n") if _clean_line(x)]
    if not lines:
        return None

    first = lines[0]

    if _is_numbered_clause_start(first):
        return first[:120]

    if _is_heading(first):
        return first[:120]

    return None


def _split_oversized_clause(text: str, max_chars: int) -> List[str]:
    text = _clean_text(text)
    if not text:
        return []

    if len(text) <= max_chars:
        return [text]

    # Prefer split by subclauses first
    lines = [_clean_line(x) for x in text.split("\n") if _clean_line(x)]
    if not lines:
        return [text]

    parts: List[str] = []
    current: List[str] = []

    for line in lines:
        if current and _is_subclause_line(line):
            candidate = "\n".join(current).strip()
            if candidate:
                parts.append(candidate)
            current = [line]
        else:
            current.append(line)

    if current:
        parts.append("\n".join(current).strip())

    if len(parts) > 1:
        final_parts: List[str] = []
        for p in parts:
            if len(p) <= max_chars:
                final_parts.append(_clean_text(p))
            else:
                final_parts.extend(_split_oversized_clause_by_sentence(p, max_chars))
        return [p for p in final_parts if p]

    return _split_oversized_clause_by_sentence(text, max_chars)


def _split_oversized_clause_by_sentence(text: str, max_chars: int) -> List[str]:
    text = _clean_text(text)
    if len(text) <= max_chars:
        return [text]

    sentences = [s.strip() for s in re.split(r"(?<=[\.\?!;])\s+", text) if s.strip()]
    if len(sentences) <= 1:
        return [text[i:i + max_chars].strip() for i in range(0, len(text), max_chars) if text[i:i + max_chars].strip()]

    out: List[str] = []
    current = ""

    for sent in sentences:
        candidate = sent if not current else current + " " + sent
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                out.append(_clean_text(current))
            current = sent

    if current:
        out.append(_clean_text(current))

    return [x for x in out if x]


def _extract_residual_from_full_text(full_text: str) -> str:
    marker = "RESIDUAL_PAGE_TEXT:"
    if marker not in full_text:
        return ""

    idx = full_text.find(marker)
    residual = full_text[idx + len(marker):].strip()
    return _clean_text(residual)


def _extract_body_from_page(page: Any) -> str:
    body_text = getattr(page, "body_text", "") or ""
    return _clean_text(body_text)


def _extract_tables_from_page(page: Any) -> List[str]:
    table_texts = getattr(page, "table_texts", None) or []
    cleaned = []
    for t in table_texts:
        t = _clean_text(t)
        if t:
            cleaned.append(t)
    return cleaned


def _body_to_clause_chunks(body_text: str, max_chars: int) -> List[str]:
    if not body_text:
        return []

    lines = [_clean_line(x) for x in body_text.split("\n")]
    lines = [x for x in lines if x]

    if not lines:
        return []

    chunks: List[str] = []
    current: List[str] = []

    for line in lines:
        if _is_numbered_clause_start(line):
            if current:
                chunk_text = _clean_text("\n".join(current))
                if chunk_text:
                    chunks.append(chunk_text)
            current = [line]
        else:
            if not current:
                current = [line]
            else:
                current.append(line)

    if current:
        chunk_text = _clean_text("\n".join(current))
        if chunk_text:
            chunks.append(chunk_text)

    final_chunks: List[str] = []
    for ch in chunks:
        if len(ch) <= max_chars:
            final_chunks.append(ch)
        else:
            final_chunks.extend(_split_oversized_clause(ch, max_chars=max_chars))

    return [x for x in final_chunks if x]


def _table_to_chunks(table_texts: List[str], max_chars: int) -> List[str]:
    chunks: List[str] = []

    for table_text in table_texts:
        if len(table_text) <= max_chars:
            chunks.append(table_text)
        else:
            chunks.extend(_split_oversized_clause_by_sentence(table_text, max_chars))

    return [x for x in chunks if x]


def chunk_pages(
    pages: List[Any],
    max_chars: int = DEFAULT_MAX_CHARS,
) -> List[Chunk]:
    chunks: List[Chunk] = []

    for page in pages:
        page_num = getattr(page, "page_num", None)

        body_text = _extract_body_from_page(page)
        table_texts = _extract_tables_from_page(page)
        full_text = getattr(page, "full_text", "") or ""
        residual_text = _extract_residual_from_full_text(full_text)

        page_chunk_texts: List[str] = []

        # 1. Main legal body -> clause chunks
        page_chunk_texts.extend(_body_to_clause_chunks(body_text, max_chars=max_chars))

        # 2. Tables -> separate chunks
        page_chunk_texts.extend(_table_to_chunks(table_texts, max_chars=max_chars))

        # 3. Residual -> at most one fallback chunk per page
        if residual_text:
            if len(residual_text) <= max_chars:
                page_chunk_texts.append(residual_text)
            else:
                page_chunk_texts.extend(_split_oversized_clause_by_sentence(residual_text, max_chars))

        for idx, text in enumerate(page_chunk_texts, start=1):
            text = _clean_text(text)
            if not text:
                continue

            chunks.append(
                Chunk(
                    chunk_id=f"p{page_num}_c{idx}",
                    page_num=page_num,
                    text=text,
                    section_hint=_infer_section_hint(text),
                )
            )

    return chunks