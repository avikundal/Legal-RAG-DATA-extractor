from pathlib import Path

from src.legal_extract.schemas import Chunk, OutputType, RetrievedChunk
from src.legal_extract.service import extract


TEST_DOCS_DIR = Path(__file__).resolve().parents[1] / "test_docs"
POLICY_PDF = TEST_DOCS_DIR / "PolicySoftCopy_1105948950.pdf"


class FakeLLMClient:
    def __init__(self, response_text: str):
        self.response_text = response_text

    def generate(self, prompt: str) -> str:
        return self.response_text


class FakeRetriever:
    def __init__(self, retrieved_chunks):
        self._retrieved_chunks = retrieved_chunks
        self.index_called = False

    def index(self, chunks):
        self.index_called = True

    def retrieve(self, query: str, top_k: int = 5):
        return self._retrieved_chunks[:top_k]


def make_fake_retrieved_chunks():
    chunk = Chunk(
        chunk_id="p1_c1",
        page_num=1,
        text="Policy Number: 920292623071050303. TOTAL PREMIUM PAYABLE (₹) 443.",
        section_hint="Policy Schedule",
    )
    return [
        RetrievedChunk(
            chunk=chunk,
            rank=1,
            combined_score=0.99,
            bm25_score=0.9,
            semantic_score=0.95,
        )
    ]


def test_service_extracts_policy_number_with_fake_llm():
    fake_llm = FakeLLMClient(
        '{"value":"920292623071050303","found":true,"evidence_chunk_ids":["p1_c1"]}'
    )
    fake_retriever = FakeRetriever(make_fake_retrieved_chunks())

    result = extract(
        pdf=str(POLICY_PDF),
        query="What is the policy number?",
        output_type=OutputType.STRING,
        llm_client=fake_llm,
        retriever=fake_retriever,
    )

    assert result["found"] is True
    assert result["value"] == "920292623071050303"
    assert result["error"] is None
    assert len(result["sources"]) == 1
    assert result["sources"][0]["page"] == 1
    assert "920292623071050303" in result["sources"][0]["snippet"]


def test_service_returns_not_found_when_llm_says_not_found():
    fake_llm = FakeLLMClient(
        '{"value":null,"found":false,"evidence_chunk_ids":[]}'
    )
    fake_retriever = FakeRetriever(make_fake_retrieved_chunks())

    result = extract(
        pdf=str(POLICY_PDF),
        query="What is the deductible amount?",
        output_type=OutputType.NUMBER,
        llm_client=fake_llm,
        retriever=fake_retriever,
    )

    assert result["found"] is False
    assert result["value"] is None
    assert result["sources"] == []
    assert result["error"] is None


def test_service_returns_validation_error_for_wrong_type():
    fake_llm = FakeLLMClient(
        '{"value":"not a number","found":true,"evidence_chunk_ids":["p1_c1"]}'
    )
    fake_retriever = FakeRetriever(make_fake_retrieved_chunks())

    result = extract(
        pdf=str(POLICY_PDF),
        query="What is the total premium payable?",
        output_type=OutputType.NUMBER,
        llm_client=fake_llm,
        retriever=fake_retriever,
    )

    assert result["found"] is False
    assert result["value"] is None
    assert result["error"] is not None
    assert result["error"]["code"] == "VALIDATION_FAILED"
