from __future__ import annotations

import io
import re
from collections import Counter
from typing import List, Tuple, Union

import fitz  # PyMuPDF
import pdfplumber

from .schemas import PageText


def _clean_line(line: str) -> str:
    line = line.replace("\u00a0", " ")
    line = re.sub(r"[ \t]{2,}", " ", line).strip()
    return line


def _clean_page_text(text: str) -> str:
    if not text:
        return ""

    text = text.replace("\r\n", "\n").replace("\r", "\n")

    cleaned_lines = []
    for line in text.split("\n"):
        line = _clean_line(line)
        cleaned_lines.append(line)

    text = "\n".join(cleaned_lines)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def _table_to_text(table: List[List[str]]) -> str:
    rows = []
    for row in table:
        if not row:
            continue
        cleaned_row = [_clean_line(cell or "") for cell in row]
        cleaned_row = [c for c in cleaned_row if c]
        if cleaned_row:
            rows.append(" | ".join(cleaned_row))
    return "\n".join(rows).strip()


def _looks_like_page_furniture(line: str) -> bool:
    t = line.strip()
    if not t:
        return False

    lower = t.lower()

    patterns = [
        r"^document ref:",
        r"^page \d+ of \d+$",
        r"^consultant initials",
        r"^company initials",
        r"^signed with pandadoc",
        r"^ref\. number",
        r"^signer timestamp",
        r"^recipient verification",
        r"^email viewed$",
        r"^email verified$",
        r"^ip address$",
        r"^utc$",
        r"^sent$",
        r"^signed$",
    ]

    for p in patterns:
        if re.search(p, lower):
            return True

    if lower in {
        "confidential",
        "v 12.29.16",
        "[signature]",
        "[authorized signatory]",
    }:
        return True

    return False


def _looks_like_audit_page_line(line: str) -> bool:
    t = line.strip().lower()
    if not t:
        return False

    signals = [
        "document completed by all parties",
        "signer timestamp signature",
        "recipient verification",
        "signed with pandadoc",
        "email viewed",
        "email verified",
        "ip address",
    ]
    return any(sig in t for sig in signals)


def _is_numbered_clause_start(line: str) -> bool:
    t = line.strip()
    if not t:
        return False

    if re.match(r"^\d+\.[A-Z]", t):
        return True

    if re.match(r"^\d+\.\s*[A-Z]", t):
        return True

    if re.match(r"^\d+(\.\d+)+\s*[A-Z]", t):
        return True

    return False


def _looks_like_content_line(line: str) -> bool:
    t = line.strip()
    if not t:
        return False

    if _is_numbered_clause_start(t):
        return True

    if re.match(r"^[a-zA-Z][.)]\s+\S+", t):
        return True

    if re.match(r"^\([a-zA-Z0-9]+\)\s+\S+", t):
        return True

    if len(t.split()) >= 4:
        return True

    if any(ch in t for ch in ["(", ")", "“", "”", ":", ","]):
        return True

    if re.search(r"\b(company|consultant|agreement|party|parties|date|name|title)\b", t, flags=re.IGNORECASE):
        return True

    if t.isupper() and 1 <= len(t.split()) <= 12:
        return True

    return False


def _extract_text_blocks_pymupdf(doc: fitz.Document) -> List[str]:
    page_texts: List[str] = []

    for page in doc:
        blocks = page.get_text("blocks")
        if not blocks:
            page_texts.append("")
            continue

        # block tuple: (x0, y0, x1, y1, text, block_no, block_type)
        blocks_sorted = sorted(blocks, key=lambda b: (round(b[1], 1), round(b[0], 1)))

        parts: List[str] = []
        for block in blocks_sorted:
            text = block[4] or ""
            text = text.strip()
            if not text:
                continue
            parts.append(text)

        page_texts.append("\n".join(parts).strip())

    return page_texts


def _collect_repeated_lines_from_page_texts(page_texts: List[str]) -> set[str]:
    counter: Counter[str] = Counter()

    for raw_text in page_texts:
        raw_text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
        seen_on_page = set()

        for line in raw_text.split("\n"):
            line = _clean_line(line)
            if not line:
                continue

            lower = line.lower()
            if len(lower) > 120:
                continue

            seen_on_page.add(lower)

        for line in seen_on_page:
            counter[line] += 1

    return {line for line, freq in counter.items() if freq >= 2}


def _split_body_lines(raw_body_text: str, repeated_lines: set[str]) -> Tuple[str, str]:
    if not raw_body_text:
        return "", ""

    raw_body_text = raw_body_text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [_clean_line(x) for x in raw_body_text.split("\n")]

    audit_like_count = sum(1 for line in lines if _looks_like_audit_page_line(line))
    if audit_like_count >= 3:
        body_text = "\n".join([x for x in lines if x]).strip()
        return _clean_page_text(body_text), ""

    clean_lines: List[str] = []
    residual_lines: List[str] = []

    for i, line in enumerate(lines):
        if not line:
            if clean_lines and clean_lines[-1] != "":
                clean_lines.append("")
            continue

        lower = line.lower()
        prev_line = lines[i - 1] if i > 0 else ""
        next_line = lines[i + 1] if i + 1 < len(lines) else ""

        if _looks_like_page_furniture(line):
            residual_lines.append(line)
            continue

        if lower in repeated_lines:
            if _looks_like_content_line(line):
                clean_lines.append(line)
            else:
                residual_lines.append(line)
            continue

        if not _looks_like_content_line(line):
            attached_to_content = (
                _looks_like_content_line(prev_line) or
                _looks_like_content_line(next_line)
            )
            if attached_to_content:
                clean_lines.append(line)
            else:
                residual_lines.append(line)
            continue

        clean_lines.append(line)

    clean_body_text = "\n".join(clean_lines)
    clean_body_text = re.sub(r"\n{3,}", "\n\n", clean_body_text).strip()

    residual_text = "\n".join(residual_lines)
    residual_text = re.sub(r"\n{3,}", "\n\n", residual_text).strip()

    return clean_body_text, residual_text


def _extract_tables_pdfplumber(pdf: Union[str, bytes]) -> List[List[str]]:
    all_table_texts: List[List[str]] = []

    if isinstance(pdf, bytes):
        pdf_stream = io.BytesIO(pdf)
        with pdfplumber.open(pdf_stream) as doc:
            for page in doc.pages:
                table_texts: List[str] = []
                tables = page.extract_tables() or []
                for table in tables:
                    table_text = _table_to_text(table)
                    table_text = _clean_page_text(table_text)
                    if table_text:
                        table_texts.append(table_text)
                all_table_texts.append(table_texts)
        return all_table_texts

    if isinstance(pdf, str):
        with pdfplumber.open(pdf) as doc:
            for page in doc.pages:
                table_texts: List[str] = []
                tables = page.extract_tables() or []
                for table in tables:
                    table_text = _table_to_text(table)
                    table_text = _clean_page_text(table_text)
                    if table_text:
                        table_texts.append(table_text)
                all_table_texts.append(table_texts)
        return all_table_texts

    raise TypeError("pdf must be either a file path (str) or raw bytes")


def _extract_pages(pdf: Union[str, bytes]) -> List[PageText]:
    pages: List[PageText] = []

    if isinstance(pdf, bytes):
        fitz_doc = fitz.open(stream=pdf, filetype="pdf")
    elif isinstance(pdf, str):
        fitz_doc = fitz.open(pdf)
    else:
        raise TypeError("pdf must be either a file path (str) or raw bytes")

    try:
        raw_page_texts = _extract_text_blocks_pymupdf(fitz_doc)
    finally:
        fitz_doc.close()

    repeated_lines = _collect_repeated_lines_from_page_texts(raw_page_texts)
    all_table_texts = _extract_tables_pdfplumber(pdf)

    for idx, raw_body_text in enumerate(raw_page_texts, start=1):
        clean_body_text, residual_text = _split_body_lines(raw_body_text, repeated_lines)

        clean_body_text = _clean_page_text(clean_body_text)
        residual_text = _clean_page_text(residual_text)

        table_texts = all_table_texts[idx - 1] if idx - 1 < len(all_table_texts) else []

        full_parts = []
        if clean_body_text:
            full_parts.append(clean_body_text)

        if table_texts:
            full_parts.extend(table_texts)

        if residual_text:
            full_parts.append("RESIDUAL_PAGE_TEXT:\n" + residual_text)

        full_text = "\n\n".join(full_parts).strip()

        pages.append(
            PageText(
                page_num=idx,
                body_text=clean_body_text,
                table_texts=table_texts,
                full_text=full_text,
            )
        )

    return pages


def parse_pdf(pdf: Union[str, bytes]) -> List[PageText]:
    try:
        return _extract_pages(pdf)
    except Exception as e:
        raise ValueError(f"Failed to parse PDF: {str(e)}")