from __future__ import annotations

import re
from typing import Dict, List, Optional, Set

from .chunker import chunk_pages
from .extractor import build_extraction_prompt, parse_extraction_response
from .llm_client import LLMClientError, OpenAILLMClient
from .pdf_parser import parse_pdf
from .retriever import HybridRetriever
from .schemas import (
    ErrorInfo,
    ExampleItem,
    ExtractRequest,
    ExtractResponse,
    OutputType,
    RetrievedChunk,
    SourceSnippet,
)
from .validator import ValidationError, validate_and_normalize


DEFAULT_TOP_K = 8
DEFAULT_SNIPPET_MAX_CHARS = 300


STOPWORDS = {
    "what", "is", "the", "a", "an", "of", "for", "to", "in", "on", "at", "by",
    "who", "when", "where", "does", "do", "did", "was", "were", "are", "and",
    "or", "this", "that", "these", "those", "all", "list", "agreement", "document",
    "contract", "clause", "term",
}


def _normalize_inline(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _trim_text(text: str, max_chars: int = DEFAULT_SNIPPET_MAX_CHARS) -> str:
    text = _normalize_inline(text)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z0-9]+", text.lower())


def _query_terms(query: str) -> Set[str]:
    toks = _tokenize(query)
    return {t for t in toks if t not in STOPWORDS and len(t) > 1}


def _value_variants(raw_value, normalized_value) -> List[str]:
    vals: List[str] = []

    for v in [raw_value, normalized_value]:
        if v is None:
            continue
        if isinstance(v, list):
            continue
        s = str(v).strip()
        if s:
            vals.append(s)

    # dedupe while preserving order
    seen = set()
    out = []
    for v in vals:
        k = v.lower()
        if k not in seen:
            seen.add(k)
            out.append(v)
    return out


def _is_clause_start(line: str) -> bool:
    t = line.strip()
    if not t:
        return False

    if re.match(r"^\d+(\.\d+)*[.)]?\s*", t):
        return True

    if re.match(r"^[a-zA-Z][.)]\s+", t):
        return True

    if re.match(r"^\([a-zA-Z0-9]+\)\s+", t):
        return True

    if t.isupper() and len(t.split()) <= 14:
        return True

    return False


def _split_chunk_into_passages(chunk_text: str) -> List[str]:
    text = chunk_text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return []

    raw_lines = [ln.rstrip() for ln in text.split("\n")]

    passages: List[str] = []
    current: List[str] = []

    for raw_line in raw_lines:
        line = raw_line.strip()

        if not line:
            if current:
                passages.append("\n".join(current).strip())
                current = []
            continue

        if current and _is_clause_start(line):
            passages.append("\n".join(current).strip())
            current = [line]
        else:
            current.append(line)

    if current:
        passages.append("\n".join(current).strip())

    return [p for p in passages if p.strip()]


def _score_passage(
    passage: str,
    query: str,
    query_terms: Set[str],
    value_texts: List[str],
) -> float:
    score = 0.0

    passage_inline = _normalize_inline(passage)
    lower_passage = passage_inline.lower()
    lower_query = query.lower()

    # exact query phrase
    if lower_query in lower_passage:
        score += 6.0

    # query token overlap
    if query_terms:
        passage_terms = set(_tokenize(passage_inline))
        overlap = len(query_terms & passage_terms)
        score += 4.0 * (overlap / len(query_terms))

    # boosts for important legal query words
    if "non compete" in lower_query and "non-compete" in lower_passage:
        score += 4.0
    if "non compete" in lower_query and "non compete" in lower_passage:
        score += 4.0
    if "govern" in lower_query and ("applicable law" in lower_passage or "governing law" in lower_passage):
        score += 3.0
    if "consultant" in lower_query and "consultant" in lower_passage:
        score += 2.0

    # value presence is secondary, not primary
    for v in value_texts:
        lv = v.lower()
        if lv and lv in lower_passage:
            score += 2.0

    # prefer passages that are neither tiny nor huge
    n = len(passage_inline)
    if 80 <= n <= 1200:
        score += 0.5

    return score


def _build_snippet_from_chunk(
    chunk_text: str,
    query: str,
    normalized_value,
    raw_value=None,
    max_chars: int = DEFAULT_SNIPPET_MAX_CHARS,
) -> str:
    if not chunk_text or not chunk_text.strip():
        return ""

    passages = _split_chunk_into_passages(chunk_text)
    if not passages:
        return _trim_text(chunk_text, max_chars=max_chars)

    q_terms = _query_terms(query)
    value_texts = _value_variants(raw_value, normalized_value)

    best_passage = None
    best_score = -1.0

    for passage in passages:
        s = _score_passage(
            passage=passage,
            query=query,
            query_terms=q_terms,
            value_texts=value_texts,
        )
        if s > best_score:
            best_score = s
            best_passage = passage

    if not best_passage:
        return _trim_text(chunk_text, max_chars=max_chars)

    return _trim_text(best_passage, max_chars=max_chars)


def _retrieved_chunk_map(retrieved_chunks: List[RetrievedChunk]) -> Dict[str, RetrievedChunk]:
    return {item.chunk.chunk_id: item for item in retrieved_chunks}


class ExtractionService:
    def __init__(
        self,
        llm_client: Optional[OpenAILLMClient] = None,
        retriever: Optional[HybridRetriever] = None,
        top_k: int = DEFAULT_TOP_K,
    ) -> None:
        self.llm_client = llm_client or OpenAILLMClient()
        self.retriever = retriever or HybridRetriever()
        self.top_k = top_k

    def run(self, request: ExtractRequest) -> ExtractResponse:
        try:
            pages = parse_pdf(request.pdf)
            chunks = chunk_pages(pages)

            if not chunks:
                return ExtractResponse(
                    value=None,
                    found=False,
                    sources=[],
                    error=ErrorInfo(
                        code="NO_TEXT_EXTRACTED",
                        message="No usable text chunks were extracted from the PDF.",
                    ),
                )

            self.retriever.index(chunks)
            retrieved = self.retriever.retrieve(
                query=request.query,
                top_k=self.top_k,
            )

            if not retrieved:
                return ExtractResponse(
                    value=None,
                    found=False,
                    sources=[],
                    error=ErrorInfo(
                        code="NO_RELEVANT_EVIDENCE",
                        message="No relevant evidence chunks were retrieved for the query.",
                    ),
                )

            prompt = build_extraction_prompt(
                query=request.query,
                output_type=request.output_type,
                retrieved_chunks=retrieved,
                examples=request.examples,
            )

            allowed_chunk_ids = {item.chunk.chunk_id for item in retrieved}
            raw_text = self.llm_client.generate(prompt)
            raw_extraction = parse_extraction_response(
                raw_text,
                allowed_chunk_ids=allowed_chunk_ids,
            )

            if not raw_extraction.found:
                return ExtractResponse(
                    value=None,
                    found=False,
                    sources=[],
                    error=None,
                )

            normalized_value, _ = validate_and_normalize(
                raw_extraction.value,
                request.output_type,
            )

            retrieved_map = _retrieved_chunk_map(retrieved)
            valid_evidence_ids = [
                cid for cid in raw_extraction.evidence_chunk_ids if cid in retrieved_map
            ]

            if not valid_evidence_ids:
                return ExtractResponse(
                    value=None,
                    found=False,
                    sources=[],
                    error=ErrorInfo(
                        code="WEAK_EVIDENCE",
                        message="Model returned an answer without valid supporting evidence.",
                    ),
                )

            sources: List[SourceSnippet] = []
            seen_pairs = set()

            for cid in valid_evidence_ids:
                item = retrieved_map[cid]
                snippet = _build_snippet_from_chunk(
                    item.chunk.text,
                    query=request.query,
                    normalized_value=normalized_value,
                    raw_value=raw_extraction.value,
                )

                pair = (item.chunk.page_num, snippet)
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)

                sources.append(
                    SourceSnippet(
                        page=item.chunk.page_num,
                        snippet=snippet,
                    )
                )

            return ExtractResponse(
                value=normalized_value,
                found=True,
                sources=sources,
                error=None,
            )

        except ValidationError as e:
            return ExtractResponse(
                value=None,
                found=False,
                sources=[],
                error=ErrorInfo(
                    code="VALIDATION_FAILED",
                    message=str(e),
                ),
            )

        except LLMClientError as e:
            return ExtractResponse(
                value=None,
                found=False,
                sources=[],
                error=ErrorInfo(
                    code="LLM_ERROR",
                    message=str(e),
                ),
            )

        except Exception as e:
            return ExtractResponse(
                value=None,
                found=False,
                sources=[],
                error=ErrorInfo(
                    code="SERVICE_ERROR",
                    message=str(e),
                ),
            )


def extract(
    pdf,
    query: str,
    output_type: OutputType,
    examples: Optional[List[dict]] = None,
    llm_client: Optional[OpenAILLMClient] = None,
    retriever: Optional[HybridRetriever] = None,
    top_k: int = DEFAULT_TOP_K,
) -> dict:
    example_models = [ExampleItem(**ex) for ex in examples] if examples else None

    request = ExtractRequest(
        pdf=pdf,
        query=query,
        output_type=output_type,
        examples=example_models,
    )

    service = ExtractionService(
        llm_client=llm_client,
        retriever=retriever,
        top_k=top_k,
    )

    response = service.run(request)
    return response.model_dump()