from __future__ import annotations

import json
from typing import List, Optional, Set

from .schemas import ExampleItem, OutputType, RawExtraction, RetrievedChunk


def _output_type_to_text(output_type: OutputType) -> str:
    return output_type.value


def _format_examples(examples: Optional[List[ExampleItem]]) -> str:
    if not examples:
        return ""

    lines: List[str] = ["Few-shot examples:"]

    for idx, ex in enumerate(examples, start=1):
        lines.append(f"Example {idx}")
        lines.append("Input:")
        lines.append(json.dumps(ex.input, ensure_ascii=False, indent=2))
        lines.append("Output:")
        lines.append(json.dumps(ex.output, ensure_ascii=False, indent=2))
        lines.append("")

    return "\n".join(lines).strip()


def _format_evidence_blocks(retrieved_chunks: List[RetrievedChunk]) -> str:
    if not retrieved_chunks:
        return "No evidence provided."

    blocks: List[str] = []

    for item in retrieved_chunks:
        lines = [
            f"Chunk ID: {item.chunk.chunk_id}",
            f"Page: {item.chunk.page_num}",
        ]

        if item.chunk.section_hint:
            lines.append(f"Section: {item.chunk.section_hint}")

        lines.append("Text:")
        lines.append(item.chunk.text)

        blocks.append("\n".join(lines))

    return "\n\n---\n\n".join(blocks)


def build_extraction_prompt(
    query: str,
    output_type: OutputType,
    retrieved_chunks: List[RetrievedChunk],
    examples: Optional[List[ExampleItem]] = None,
) -> str:
    type_text = _output_type_to_text(output_type)
    examples_text = _format_examples(examples)
    evidence_text = _format_evidence_blocks(retrieved_chunks)

    parts: List[str] = [
        "You are extracting one field from a legal document.",
        "",
        "Use only the evidence below.",
        "Do not use outside knowledge.",
        "If the answer is not clearly supported, return found=false.",
        "If the evidence is conflicting or ambiguous, return found=false.",
        "Return strict JSON only. No markdown. No explanation.",
        "",
        f"Query: {query}",
        f"Output type: {type_text}",
        "",
        "Return exactly this JSON shape:",
        "{",
        '  "value": <value or null>,',
        '  "found": <true or false>,',
        '  "evidence_chunk_ids": <array of chunk ids>',
        "}",
        "",
        "Rules:",
        '- If found=false, set "value" to null and "evidence_chunk_ids" to [].',
        '- Use only chunk IDs from the evidence below.',
        '- For array types, return an array.',
        '- For number, return a numeric value if clearly extractable.',
        '- For date, return the date text from evidence.',
        '- Do not invent missing information.',
        '- For entity lists such as parties, return actual person or organization names, not role labels like "Company" or "Consultant".',
        '- For party queries, prefer names found in the opening part of the agreement where the parties are introduced.',
        '- If a role label and a real name both appear, prefer the real name.',
        '- For named parties in an agreement, include both the organization and the person if both are explicitly named in the evidence.',
    ]

    if examples_text:
        parts.extend(["", examples_text])

    parts.extend(["", "Evidence:", evidence_text])

    return "\n".join(parts).strip()


def _strip_code_fences(text: str) -> str:
    text = text.strip()

    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    return text


def parse_extraction_response(
    response_text: str,
    allowed_chunk_ids: Optional[Set[str]] = None,
) -> RawExtraction:
    response_text = _strip_code_fences(response_text)

    try:
        data = json.loads(response_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Model response was not valid JSON: {e}") from e

    if not isinstance(data, dict):
        raise ValueError("Model response JSON must be an object")

    found = data.get("found")
    value = data.get("value")
    evidence_chunk_ids = data.get("evidence_chunk_ids", [])

    if not isinstance(found, bool):
        raise ValueError("'found' must be a boolean")

    if not isinstance(evidence_chunk_ids, list):
        raise ValueError("'evidence_chunk_ids' must be a list")

    cleaned_chunk_ids: List[str] = []
    for idx, chunk_id in enumerate(evidence_chunk_ids):
        if not isinstance(chunk_id, str) or not chunk_id.strip():
            raise ValueError(f"Invalid chunk id at index {idx}: {chunk_id}")

        chunk_id = chunk_id.strip()

        if allowed_chunk_ids is not None and chunk_id not in allowed_chunk_ids:
            raise ValueError(f"Unknown evidence chunk id: {chunk_id}")

        cleaned_chunk_ids.append(chunk_id)

    if not found:
        return RawExtraction(
            value=None,
            found=False,
            evidence_chunk_ids=[],
            notes=[],
        )

    return RawExtraction(
        value=value,
        found=True,
        evidence_chunk_ids=cleaned_chunk_ids,
        notes=[],
    )





















# from __future__ import annotations

# import json
# from typing import List, Optional

# from .schemas import (
#     ArrayFieldSchema,
#     ExampleItem,
#     FieldSchema,
#     PrimitiveFieldSchema,
#     PrimitiveType,
#     RawExtraction,
#     RetrievedChunk,
# )


# def _schema_to_prompt_text(schema: FieldSchema) -> str:
#     """
#     Convert schema object to a compact human-readable type description for prompting.
#     """
#     if isinstance(schema, PrimitiveFieldSchema):
#         return schema.type.value

#     if isinstance(schema, ArrayFieldSchema):
#         return f"array[{schema.items.type.value}]"

#     raise ValueError(f"Unsupported schema: {schema}")


# def _format_examples(examples: Optional[List[ExampleItem]]) -> str:
#     """
#     Format few-shot examples for the prompt, if provided.
#     """
#     if not examples:
#         return "No few-shot examples provided."

#     lines: List[str] = ["Few-shot examples:"]
#     for idx, ex in enumerate(examples, start=1):
#         lines.append(f"Example {idx}:")
#         lines.append("Input:")
#         lines.append(json.dumps(ex.input, ensure_ascii=False, indent=2))
#         lines.append("Output:")
#         lines.append(json.dumps(ex.output, ensure_ascii=False, indent=2))
#     return "\n".join(lines)


# def _format_evidence_blocks(retrieved_chunks: List[RetrievedChunk]) -> str:
#     """
#     Format retrieved chunks into explicit evidence blocks for the LLM.
#     """
#     if not retrieved_chunks:
#         return "No evidence chunks provided."

#     blocks: List[str] = []
#     for item in retrieved_chunks:
#         section = item.chunk.section_hint or "None"
#         blocks.append(
#             "\n".join(
#                 [
#                     f"Chunk ID: {item.chunk.chunk_id}",
#                     f"Page: {item.chunk.page_num}",
#                     f"Section Hint: {section}",
#                     "Text:",
#                     item.chunk.text,
#                 ]
#             )
#         )

#     return "\n\n---\n\n".join(blocks)


# def build_extraction_prompt(
#     query: str,
#     output_type: FieldSchema,
#     retrieved_chunks: List[RetrievedChunk],
#     examples: Optional[List[ExampleItem]] = None,
# ) -> str:
#     """
#     Build the grounded extraction prompt.
#     """
#     type_text = _schema_to_prompt_text(output_type)
#     examples_text = _format_examples(examples)
#     evidence_text = _format_evidence_blocks(retrieved_chunks)

#     prompt = f"""
# You are a careful legal document extraction system.

# Your job:
# - Answer exactly ONE extraction query from the provided evidence.
# - Use ONLY the evidence blocks below.
# - Do NOT use outside knowledge.
# - If the answer is not clearly supported by the evidence, return found=false.
# - If the evidence is ambiguous or conflicting, return found=false.
# - The output must match the requested output type.
# - Always return STRICT JSON only. No markdown. No explanation.

# Requested query:
# {query}

# Requested output type:
# {type_text}

# Return JSON with exactly these keys:
# {{
#   "value": <value or null>,
#   "found": <true or false>,
#   "evidence_chunk_ids": <array of chunk ids supporting the answer>
# }}

# Rules:
# - If found=false, set "value" to null and "evidence_chunk_ids" to [].
# - "evidence_chunk_ids" must contain only chunk IDs from the provided evidence.
# - For string outputs, return a concise text answer.
# - For date outputs, return the date text as found in evidence; downstream normalization will handle formatting.
# - For number outputs, return the numeric value or the shortest numeric expression from evidence.
# - For array outputs, return an array.
# - Do not invent evidence chunk IDs.
# - Do not paraphrase unsupported information.

# {examples_text}

# Evidence blocks:
# {evidence_text}
# """.strip()

#     return prompt


# def parse_extraction_response(response_text: str) -> RawExtraction:
#     """
#     Parse the model response into RawExtraction.
#     Expects strict JSON text.
#     """
#     try:
#         data = json.loads(response_text)
#     except json.JSONDecodeError as e:
#         raise ValueError(f"Model response was not valid JSON: {e}") from e

#     if not isinstance(data, dict):
#         raise ValueError("Model response JSON must be an object")

#     found = data.get("found")
#     value = data.get("value")
#     evidence_chunk_ids = data.get("evidence_chunk_ids", [])

#     if not isinstance(found, bool):
#         raise ValueError("'found' must be a boolean")

#     if not isinstance(evidence_chunk_ids, list):
#         raise ValueError("'evidence_chunk_ids' must be a list")

#     for idx, chunk_id in enumerate(evidence_chunk_ids):
#         if not isinstance(chunk_id, str) or not chunk_id.strip():
#             raise ValueError(f"Invalid chunk id at index {idx}: {chunk_id}")

#     if found is False:
#         return RawExtraction(value=None, found=False, evidence_chunk_ids=[], notes=[])

#     return RawExtraction(
#         value=value,
#         found=True,
#         evidence_chunk_ids=evidence_chunk_ids,
#         notes=[],
#     )