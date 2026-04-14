from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, model_validator


class OutputType(str, Enum):
    STRING = "string"
    DATE = "date"
    NUMBER = "number"
    ARRAY_STRING = "array[string]"
    ARRAY_DATE = "array[date]"
    ARRAY_NUMBER = "array[number]"


class SourceSnippet(BaseModel):
    page: int = Field(..., ge=1, description="1-indexed PDF page number")
    snippet: str = Field(..., min_length=1, description="Exact supporting text from the PDF")


class ErrorInfo(BaseModel):
    code: str
    message: str


class ExampleItem(BaseModel):
    input: Dict[str, Any]
    output: Dict[str, Any]


class ExtractRequest(BaseModel):
    pdf: Union[str, bytes]
    query: str = Field(..., min_length=1)
    output_type: OutputType
    examples: Optional[List[ExampleItem]] = None

    @model_validator(mode="after")
    def validate_pdf(self) -> "ExtractRequest":
        if isinstance(self.pdf, str) and not self.pdf.strip():
            raise ValueError("pdf path cannot be empty")
        if isinstance(self.pdf, bytes) and len(self.pdf) == 0:
            raise ValueError("pdf bytes cannot be empty")
        return self


class ExtractResponse(BaseModel):
    value: Optional[Union[str, float, int, List[Union[str, float, int]]]] = None
    found: bool
    sources: List[SourceSnippet] = Field(default_factory=list)
    error: Optional[ErrorInfo] = None

    @model_validator(mode="after")
    def validate_response(self) -> "ExtractResponse":
        if self.found and self.value is None:
            raise ValueError("value must be present when found=True")
        if not self.found and self.value is not None:
            raise ValueError("value must be None when found=False")
        return self


class PageText(BaseModel):
    page_num: int = Field(..., ge=1)
    body_text: str = ""
    table_texts: List[str] = Field(default_factory=list)
    full_text: str = ""


class Chunk(BaseModel):
    chunk_id: str
    page_num: int = Field(..., ge=1)
    text: str = Field(..., min_length=1)
    section_hint: Optional[str] = None


class RetrievedChunk(BaseModel):
    chunk: Chunk
    rank: int = Field(..., ge=1)
    combined_score: float
    bm25_score: float
    semantic_score: float


class RawExtraction(BaseModel):
    value: Optional[Union[str, float, int, List[Union[str, float, int]]]] = None
    found: bool
    evidence_chunk_ids: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)

# from __future__ import annotations

# from enum import Enum
# from typing import Any, Dict, List, Literal, Optional, Union

# from pydantic import BaseModel, Field, model_validator


# # ============================================================
# # Output schema models
# # ============================================================

# class PrimitiveType(str, Enum):
#     STRING = "string"
#     DATE = "date"
#     NUMBER = "number"


# class PrimitiveFieldSchema(BaseModel):
#     type: PrimitiveType


# class ArrayFieldSchema(BaseModel):
#     type: Literal["array"]
#     items: PrimitiveFieldSchema


# FieldSchema = Union[PrimitiveFieldSchema, ArrayFieldSchema]


# # ============================================================
# # Public API models
# # ============================================================

# class SourceSnippet(BaseModel):
#     page: int = Field(..., ge=1, description="1-indexed PDF page number")
#     snippet: str = Field(..., min_length=1, description="Exact supporting text snippet")


# class ErrorInfo(BaseModel):
#     code: str
#     message: str


# class ChunkScoreDiagnostic(BaseModel):
#     chunk_id: str
#     page: int
#     rank: int
#     combined_score: float
#     bm25_score: float
#     semantic_score: float


# class Diagnostics(BaseModel):
#     retrieved_chunks: List[ChunkScoreDiagnostic] = Field(default_factory=list)
#     validation_notes: List[str] = Field(default_factory=list)
#     retrieval_strategy: str = "hybrid_bm25_semantic"


# class ExampleItem(BaseModel):
#     input: Dict[str, Any]
#     output: Dict[str, Any]


# class ExtractRequest(BaseModel):
#     pdf: Union[str, bytes]
#     query: str = Field(..., min_length=1)
#     output_type: FieldSchema
#     examples: Optional[List[ExampleItem]] = None

#     @model_validator(mode="after")
#     def validate_pdf(self) -> "ExtractRequest":
#         if isinstance(self.pdf, str) and not self.pdf.strip():
#             raise ValueError("pdf path cannot be empty")
#         if isinstance(self.pdf, bytes) and len(self.pdf) == 0:
#             raise ValueError("pdf bytes cannot be empty")
#         return self


# class ExtractResponse(BaseModel):
#     value: Optional[Union[str, float, int, List[Union[str, float, int]]]] = None
#     found: bool
#     sources: List[SourceSnippet] = Field(default_factory=list)
#     error: Optional[ErrorInfo] = None
#     diagnostics: Optional[Diagnostics] = None


# # ============================================================
# # Internal document models
# # ============================================================

# class PageText(BaseModel):
#     page_num: int = Field(..., ge=1)
#     text: str = Field(..., min_length=0)


# class Chunk(BaseModel):
#     chunk_id: str
#     page_num: int = Field(..., ge=1)
#     text: str = Field(..., min_length=1)
#     section_hint: Optional[str] = None


# class RetrievedChunk(BaseModel):
#     chunk: Chunk
#     rank: int = Field(..., ge=1)
#     combined_score: float
#     bm25_score: float
#     semantic_score: float


# # ============================================================
# # Internal extraction models
# # ============================================================

# class RawExtraction(BaseModel):
#     value: Optional[Any] = None
#     found: bool
#     evidence_chunk_ids: List[str] = Field(default_factory=list)
#     notes: List[str] = Field(default_factory=list)