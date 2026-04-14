from pathlib import Path

from src.legal_extract.chunker import chunk_pages
from src.legal_extract.pdf_parser import parse_pdf


TEST_DOCS_DIR = Path(__file__).resolve().parents[1] / "test_docs"
AI_LEAD_PDF = TEST_DOCS_DIR / "AI Lead Assignment - 1.pdf"
POLICY_PDF = TEST_DOCS_DIR / "PolicySoftCopy_1105948950.pdf"


def test_parse_pdf_extracts_pages():
    pages = parse_pdf(str(AI_LEAD_PDF))

    assert isinstance(pages, list)
    assert len(pages) >= 1

    first_page = pages[0]
    assert first_page.page_num == 1
    assert first_page.full_text
    assert "Take-Home Assignment - 1" in first_page.full_text


def test_parse_pdf_supports_bytes_input():
    pdf_bytes = POLICY_PDF.read_bytes()
    pages = parse_pdf(pdf_bytes)

    assert isinstance(pages, list)
    assert len(pages) >= 1
    assert "Policy Number" in pages[0].full_text or "920292623071050303" in pages[0].full_text


def test_chunk_pages_builds_chunks():
    pages = parse_pdf(str(AI_LEAD_PDF))
    chunks = chunk_pages(pages)

    assert isinstance(chunks, list)
    assert len(chunks) > 0

    first_chunk = chunks[0]
    assert first_chunk.chunk_id.startswith("p1_c")
    assert first_chunk.page_num == 1
    assert isinstance(first_chunk.text, str)
    assert first_chunk.text.strip()


def test_chunk_pages_contains_assignment_title_in_some_chunk():
    pages = parse_pdf(str(AI_LEAD_PDF))
    chunks = chunk_pages(pages)

    joined = "\n".join(chunk.text for chunk in chunks)
    assert "Take-Home Assignment - 1" in joined


def test_chunk_pages_contains_policy_premium_chunk():
    pages = parse_pdf(str(POLICY_PDF))
    chunks = chunk_pages(pages)

    texts = [chunk.text for chunk in chunks]
    assert any("TOTAL PREMIUM PAYABLE" in t or "443" in t for t in texts)
