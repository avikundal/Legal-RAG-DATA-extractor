from src.legal_extract.extractor import build_extraction_prompt, parse_extraction_response
from src.legal_extract.schemas import Chunk, OutputType, RetrievedChunk


def test_build_prompt_contains_query_and_type():
    chunks = [
        RetrievedChunk(
            chunk=Chunk(chunk_id="p1_c1", page_num=1, text="The consultant is Avijit Kundal.", section_hint="PARTIES"),
            rank=1,
            combined_score=1.0,
            bm25_score=1.0,
            semantic_score=1.0,
        )
    ]

    prompt = build_extraction_prompt(
        query="Who is the consultant?",
        output_type=OutputType.STRING,
        retrieved_chunks=chunks,
        examples=None,
    )

    assert "Who is the consultant?" in prompt
    assert "Output type: string" in prompt
    assert "Chunk ID: p1_c1" in prompt


def test_parse_extraction_response_accepts_valid_json():
    response = '{"value":"Avijit Kundal","found":true,"evidence_chunk_ids":["p1_c1"]}'
    parsed = parse_extraction_response(response, allowed_chunk_ids={"p1_c1"})

    assert parsed.found is True
    assert parsed.value == "Avijit Kundal"
    assert parsed.evidence_chunk_ids == ["p1_c1"]
