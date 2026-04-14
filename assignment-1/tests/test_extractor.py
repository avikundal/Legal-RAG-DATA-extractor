import pytest

from src.legal_extract.extractor import build_extraction_prompt, parse_extraction_response
from src.legal_extract.schemas import Chunk, OutputType, RetrievedChunk


def make_retrieved_chunks():
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
            combined_score=0.95,
            bm25_score=0.9,
            semantic_score=0.93,
        )
    ]


def test_build_extraction_prompt_contains_query_and_chunk():
    retrieved = make_retrieved_chunks()

    prompt = build_extraction_prompt(
        query="What is the policy number?",
        output_type=OutputType.STRING,
        retrieved_chunks=retrieved,
        examples=None,
    )

    assert "What is the policy number?" in prompt
    assert "Output type: string" in prompt
    assert "Chunk ID: p1_c1" in prompt


def test_parse_extraction_response_success():
    response = parse_extraction_response(
        '{"value":"920292623071050303","found":true,"evidence_chunk_ids":["p1_c1"]}',
        allowed_chunk_ids={"p1_c1"},
    )

    assert response.found is True
    assert response.value == "920292623071050303"
    assert response.evidence_chunk_ids == ["p1_c1"]


def test_parse_extraction_response_not_found():
    response = parse_extraction_response(
        '{"value":null,"found":false,"evidence_chunk_ids":[]}',
        allowed_chunk_ids={"p1_c1"},
    )

    assert response.found is False
    assert response.value is None
    assert response.evidence_chunk_ids == []


def test_parse_extraction_response_rejects_unknown_chunk_id():
    with pytest.raises(ValueError):
        parse_extraction_response(
            '{"value":"920292623071050303","found":true,"evidence_chunk_ids":["p9_c9"]}',
            allowed_chunk_ids={"p1_c1"},
        )


def test_parse_extraction_response_requires_list_chunk_ids():
    with pytest.raises(ValueError):
        parse_extraction_response(
            '{"value":"920292623071050303","found":true,"evidence_chunk_ids":"p1_c1"}',
            allowed_chunk_ids={"p1_c1"},
        )
