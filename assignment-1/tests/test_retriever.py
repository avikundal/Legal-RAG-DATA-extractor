from src.legal_extract.chunker import chunk_pages
from src.legal_extract.pdf_parser import parse_pdf
from src.legal_extract.retriever import HybridRetriever

PDF_PATH = "test_docs/CHETU-NDA_Consultant-India Avijit Kundal.pdf"


def test_retriever_returns_results():
    pages = parse_pdf(PDF_PATH)
    chunks = chunk_pages(pages)

    retriever = HybridRetriever()
    retriever.index(chunks)
    results = retriever.retrieve("What is the hourly compensation?", top_k=3)

    assert len(results) == 3
    assert results[0].rank == 1
    assert retriever.semantic_backend_name in {
        "sklearn_tfidf_fallback",
        "sentence_transformer:sentence-transformers/all-MiniLM-L6-v2",
        "sentence_transformer:BAAI/bge-large-en-v1.5",
}

def test_retriever_finds_non_compete_chunk():
    pages = parse_pdf(PDF_PATH)
    chunks = chunk_pages(pages)

    retriever = HybridRetriever()
    retriever.index(chunks)
    results = retriever.retrieve("What is the non-compete duration?", top_k=5)

    joined = "\n".join(item.chunk.text.lower() for item in results)
    assert "non-compete" in joined or "compete" in joined
