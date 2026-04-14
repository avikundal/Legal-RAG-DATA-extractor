from src.legal_extract.chunker import chunk_pages
from src.legal_extract.pdf_parser import parse_pdf

PDF_PATH = "test_docs/CHETU-NDA_Consultant-India Avijit Kundal.pdf"


def test_parse_pdf_extracts_pages():
    pages = parse_pdf(PDF_PATH)
    assert len(pages) >= 1
    assert pages[0].page_num == 1
    assert "AGREEMENT FOR CONSULTING SERVICES" in pages[0].full_text


def test_chunk_pages_builds_chunks():
    pages = parse_pdf(PDF_PATH)
    chunks = chunk_pages(pages)
    assert len(chunks) >= 5
    assert chunks[0].chunk_id.startswith("p1_c")
    assert all(chunk.text.strip() for chunk in chunks)
