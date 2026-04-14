from pathlib import Path

from src.legal_extract.chunker import chunk_pages
from src.legal_extract.pdf_parser import parse_pdf
from src.legal_extract.retriever import HybridRetriever


TEST_DOCS_DIR = Path(__file__).resolve().parents[1] / "test_docs"
POLICY_PDF = TEST_DOCS_DIR / "PolicySoftCopy_1105948950.pdf"
LOAN_PDF = TEST_DOCS_DIR / "Loan Documentation - Customer copy_KB251222XCOIZ.pdf"


def test_retriever_returns_results():
    pages = parse_pdf(str(POLICY_PDF))
    chunks = chunk_pages(pages)

    retriever = HybridRetriever(model_name="BAAI/bge-large-en-v1.5")
    retriever.index(chunks)

    results = retriever.retrieve("What is the total premium payable?", top_k=3)

    assert isinstance(results, list)
    assert len(results) > 0

    top = results[0]
    assert top.rank == 1
    assert top.chunk.text.strip()


def test_retriever_finds_premium_chunk():
    pages = parse_pdf(str(POLICY_PDF))
    chunks = chunk_pages(pages)

    retriever = HybridRetriever(model_name="BAAI/bge-large-en-v1.5")
    retriever.index(chunks)

    results = retriever.retrieve("What is the total premium payable?", top_k=5)

    retrieved_text = "\n".join(item.chunk.text for item in results)
    assert "TOTAL PREMIUM PAYABLE" in retrieved_text or "443" in retrieved_text


def test_retriever_finds_policy_number_chunk():
    pages = parse_pdf(str(POLICY_PDF))
    chunks = chunk_pages(pages)

    retriever = HybridRetriever(model_name="BAAI/bge-large-en-v1.5")
    retriever.index(chunks)

    results = retriever.retrieve("What is the policy number?", top_k=5)

    retrieved_text = "\n".join(item.chunk.text for item in results)
    assert "920292623071050303" in retrieved_text or "Policy Number" in retrieved_text


def test_retriever_finds_loan_amount_chunk():
    pages = parse_pdf(str(LOAN_PDF))
    chunks = chunk_pages(pages)

    retriever = HybridRetriever(model_name="BAAI/bge-large-en-v1.5")
    retriever.index(chunks)

    results = retriever.retrieve("What is the total loan amount?", top_k=5)

    retrieved_text = "\n".join(item.chunk.text for item in results)
    assert "27500" in retrieved_text or "Total Loan Amount" in retrieved_text
