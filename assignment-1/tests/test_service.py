from src.legal_extract.schemas import OutputType
from src.legal_extract.service import extract


class FakeLLMClient:
    def __init__(self, text: str):
        self.text = text

    def generate(self, prompt: str) -> str:
        return self.text


PDF_PATH = "test_docs/CHETU-NDA_Consultant-India Avijit Kundal.pdf"


def test_service_extracts_consultant_with_fake_llm():
    fake_llm = FakeLLMClient(
        '{"value":"Avijit Kundal","found":true,"evidence_chunk_ids":["p1_c1"]}'
    )

    result = extract(
        pdf=PDF_PATH,
        query="Who is the consultant?",
        output_type=OutputType.STRING,
        llm_client=fake_llm,
    )

    assert result["found"] is True
    assert result["value"] == "Avijit Kundal"
    assert len(result["sources"]) >= 1


def test_service_returns_not_found_with_fake_llm():
    fake_llm = FakeLLMClient('{"value":null,"found":false,"evidence_chunk_ids":[]}')

    result = extract(
        pdf=PDF_PATH,
        query="What is the termination notice period?",
        output_type=OutputType.STRING,
        llm_client=fake_llm,
    )

    assert result["found"] is False
    assert result["value"] is None
