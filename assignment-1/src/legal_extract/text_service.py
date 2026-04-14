from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Set

from openai import OpenAI

from .chunker import chunk_pages
from .extractor import build_extraction_prompt, parse_extraction_response
from .retriever import HybridRetriever
from .schemas import ExampleItem, OutputType, PageText
from .validator import ValidationError, validate_and_normalize


DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")


def _get_client(client: Optional[OpenAI] = None) -> OpenAI:
    if client is not None:
        return client

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    return OpenAI(api_key=api_key)


def _call_llm(prompt: str, model: str = DEFAULT_MODEL, client: Optional[OpenAI] = None) -> str:
    client = _get_client(client)

    resp = client.responses.create(
        model=model,
        input=prompt,
        temperature=0,
    )

    return resp.output_text.strip()


def _looks_like_negative_free_text(value: Any) -> bool:
    if value is None:
        return False

    text = str(value).strip().lower()
    if not text:
        return False

    patterns = [
        r"^no[, ]",
        r"^no\.",
        r"^there is no\b",
        r"^the agreement does not\b",
        r"^this agreement does not\b",
        r"^the contract does not\b",
        r"^this contract does not\b",
        r"^not found\b",
        r"^none\b",
    ]

    return any(re.search(p, text) for p in patterns)


def extract_from_text(
    text: str,
    query: str,
    output_type: OutputType,
    examples: Optional[List[ExampleItem]] = None,
    retriever: Optional[HybridRetriever] = None,
    top_k: int = 5,
    model: str = DEFAULT_MODEL,
    client: Optional[OpenAI] = None,
) -> Dict[str, Any]:
    if not text or not str(text).strip():
        return {
            "value": None,
            "found": False,
            "sources": [],
            "error": {
                "code": "EMPTY_TEXT",
                "message": "Input text is empty.",
            },
        }

    pseudo_pages = [
        PageText(
            page_num=1,
            body_text=str(text).strip(),
            table_texts=[],
            full_text=str(text).strip(),
        )
    ]

    chunks = chunk_pages(pseudo_pages)

    if not chunks:
        return {
            "value": None,
            "found": False,
            "sources": [],
            "error": None,
        }

    if retriever is None:
        retriever = HybridRetriever(model_name="BAAI/bge-large-en-v1.5")

    retriever.index(chunks)
    retrieved_chunks = retriever.retrieve(query=query, top_k=top_k)

    if not retrieved_chunks:
        return {
            "value": None,
            "found": False,
            "sources": [],
            "error": None,
        }

    prompt = build_extraction_prompt(
        query=query,
        output_type=output_type,
        retrieved_chunks=retrieved_chunks,
        examples=examples,
    )

    allowed_chunk_ids: Set[str] = {rc.chunk.chunk_id for rc in retrieved_chunks}

    try:
        response_text = _call_llm(prompt, model=model, client=client)
        extraction = parse_extraction_response(
            response_text=response_text,
            allowed_chunk_ids=allowed_chunk_ids,
        )
    except Exception as e:
        return {
            "value": None,
            "found": False,
            "sources": [],
            "error": {
                "code": "EXTRACTION_FAILED",
                "message": str(e),
            },
        }

    if not extraction.found:
        return {
            "value": None,
            "found": False,
            "sources": [],
            "error": None,
        }

    # General safeguard: if model says found=true but value is basically a negative sentence,
    # treat it as not found. This is generic, not query-specific.
    if _looks_like_negative_free_text(extraction.value):
        return {
            "value": None,
            "found": False,
            "sources": [],
            "error": None,
        }

    try:
        normalized_value, notes = validate_and_normalize(extraction.value, output_type)
    except ValidationError as e:
        return {
            "value": None,
            "found": False,
            "sources": [],
            "error": {
                "code": "VALIDATION_FAILED",
                "message": str(e),
            },
        }

    valid_evidence_ids = set(extraction.evidence_chunk_ids or [])
    sources = []

    for rc in retrieved_chunks:
        if rc.chunk.chunk_id not in valid_evidence_ids:
            continue

        snippet = rc.chunk.text.strip()
        if len(snippet) > 350:
            snippet = snippet[:350].rstrip() + "..."

        sources.append(
            {
                "page": rc.chunk.page_num,
                "snippet": snippet,
            }
        )

    if not sources:
        for rc in retrieved_chunks[:2]:
            snippet = rc.chunk.text.strip()
            if len(snippet) > 350:
                snippet = snippet[:350].rstrip() + "..."
            sources.append(
                {
                    "page": rc.chunk.page_num,
                    "snippet": snippet,
                }
            )

    return {
        "value": normalized_value,
        "found": True,
        "sources": sources,
        "error": None,
    }