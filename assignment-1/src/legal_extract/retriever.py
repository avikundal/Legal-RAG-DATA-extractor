from __future__ import annotations

import math
import re
from typing import List, Optional, Sequence, Set

import numpy as np
from rank_bm25 import BM25Okapi

from .schemas import Chunk, RetrievedChunk


try:
    from sentence_transformers import SentenceTransformer  # type: ignore
except Exception:
    SentenceTransformer = None  # type: ignore

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
except Exception:
    TfidfVectorizer = None  # type: ignore


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[A-Za-z0-9_]+", text.lower())


def _min_max_normalize(scores: Sequence[float]) -> List[float]:
    if not scores:
        return []

    min_s = min(scores)
    max_s = max(scores)

    if math.isclose(min_s, max_s):
        return [0.0 for _ in scores]

    return [(s - min_s) / (max_s - min_s) for s in scores]


def _cosine_similarity_matrix(query_vec: np.ndarray, doc_vecs: np.ndarray) -> np.ndarray:
    query_norm = np.linalg.norm(query_vec)
    doc_norms = np.linalg.norm(doc_vecs, axis=1)

    denom = np.clip(query_norm * doc_norms, a_min=1e-12, a_max=None)
    return np.dot(doc_vecs, query_vec) / denom


def _query_terms(query: str) -> Set[str]:
    return {tok for tok in _tokenize(query) if len(tok) >= 3}


def _token_overlap_boost(query_terms: Set[str], chunk_text: str) -> float:
    if not query_terms:
        return 0.0

    chunk_terms = set(_tokenize(chunk_text))
    overlap = len(query_terms & chunk_terms)
    return overlap / len(query_terms)


def _section_hint_boost(query_terms: Set[str], section_hint: Optional[str]) -> float:
    if not query_terms or not section_hint:
        return 0.0

    hint_terms = set(_tokenize(section_hint))
    overlap = len(query_terms & hint_terms)
    if overlap == 0:
        return 0.0

    return overlap / len(query_terms)


def _phrase_boost(query: str, chunk_text: str) -> float:
    q = query.lower().strip()
    t = chunk_text.lower()

    if not q or not t:
        return 0.0

    if q in t:
        return 1.0

    q_terms = [tok for tok in _tokenize(q) if len(tok) >= 3]
    if not q_terms:
        return 0.0

    chunk_terms = set(_tokenize(t))
    matches = sum(1 for tok in q_terms if tok in chunk_terms)
    frac = matches / len(q_terms)

    return frac if frac >= 0.6 else 0.0


def _is_party_query(query: str) -> bool:
    q = query.lower()
    return any(
        term in q
        for term in [
            "party",
            "parties",
            "between whom",
            "who are the parties",
            "named parties",
        ]
    )


def _page_boost(query: str, page_num: int) -> float:
    q = query.lower()

    if _is_party_query(q):
        if page_num == 1:
            return 1.0
        return 0.0

    if any(term in q for term in ["consultant", "company", "agreement made", "effective date"]):
        if page_num == 1:
            return 0.6

    return 0.0


def _opening_recital_boost(query: str, chunk_text: str, page_num: int) -> float:
    if not _is_party_query(query):
        return 0.0

    if page_num != 1:
        return 0.0

    text = chunk_text.lower()

    signals = 0
    if "between" in text:
        signals += 1
    if "company" in text:
        signals += 1
    if "consultant" in text:
        signals += 1
    if "agreement" in text:
        signals += 1

    if signals >= 3:
        return 1.0
    if signals == 2:
        return 0.5
    return 0.0


def _is_residual_or_junk_chunk(chunk_text: str) -> bool:
    t = chunk_text.lower()

    junk_signals = [
        "residual_page_text",
        "document ref:",
        "consultant initials",
        "company initials",
        "signed with pandadoc",
        "recipient verification",
        "signer timestamp signature",
        "email viewed",
        "email verified",
        "ip address",
    ]

    return any(sig in t for sig in junk_signals)


def _tiny_chunk_penalty(chunk_text: str) -> float:
    text = chunk_text.strip()
    n = len(text)

    if n < 40:
        return 0.22
    if n < 80:
        return 0.12
    if n < 140:
        return 0.05
    return 0.0


def _residual_penalty(chunk_text: str) -> float:
    return 0.20 if _is_residual_or_junk_chunk(chunk_text) else 0.0


def _legal_label_boost(query: str, section_hint: Optional[str], chunk_text: str) -> float:
    q = query.lower()
    hint = (section_hint or "").lower()
    text = chunk_text.lower()

    score = 0.0

    if "non-compete" in q or "non compete" in q:
        if "non-compete" in hint or "non compete" in hint or "non-compete" in text or "non compete" in text:
            score += 0.35

    if "non-disparagement" in q or "non disparagement" in q or "non-disparagment" in q:
        if "non-disparagement" in hint or "non disparagement" in hint or "non-disparagment" in hint:
            score += 0.35

    if "governing law" in q or "applicable law" in q or "law governs" in q:
        if "applicable law" in hint or "applicable law" in text:
            score += 0.30

    if "compensation" in q or "hourly compensation" in q or "compensation amount" in q:
        if "compensation" in hint or "compensation" in text:
            score += 0.25

    if "consultant" in q:
        if "consultant" in hint or "consultant" in text:
            score += 0.12

    return score


class _SklearnSemanticEncoder:
    def __init__(self) -> None:
        if TfidfVectorizer is None:
            raise ImportError("scikit-learn is required for fallback semantic retrieval")
        self.vectorizer = TfidfVectorizer(ngram_range=(1, 2))

    def fit(self, texts: List[str]) -> np.ndarray:
        return self.vectorizer.fit_transform(texts).toarray().astype(np.float32)

    def encode_query(self, query: str) -> np.ndarray:
        return self.vectorizer.transform([query]).toarray()[0].astype(np.float32)


class HybridRetriever:
    def __init__(
        self,
        model_name: str = "BAAI/bge-large-en-v1.5",
        bm25_weight: float = 0.34,
        semantic_weight: float = 0.34,
        token_overlap_weight: float = 0.07,
        section_hint_weight: float = 0.03,
        phrase_weight: float = 0.05,
        page_weight: float = 0.07,
        recital_weight: float = 0.10,
        rerank_pool_size: int = 16,
    ) -> None:
        weights = [
            bm25_weight,
            semantic_weight,
            token_overlap_weight,
            section_hint_weight,
            phrase_weight,
            page_weight,
            recital_weight,
        ]

        if any(w < 0 for w in weights):
            raise ValueError("All weights must be non-negative")

        total = sum(weights)
        if total == 0:
            raise ValueError("At least one weight must be > 0")

        self.bm25_weight = bm25_weight / total
        self.semantic_weight = semantic_weight / total
        self.token_overlap_weight = token_overlap_weight / total
        self.section_hint_weight = section_hint_weight / total
        self.phrase_weight = phrase_weight / total
        self.page_weight = page_weight / total
        self.recital_weight = recital_weight / total

        self.model_name = model_name
        self.rerank_pool_size = max(6, rerank_pool_size)

        self.semantic_backend = None
        self.semantic_backend_name = "none"
        self._init_semantic_backend()

        self.chunks: List[Chunk] = []
        self.chunk_texts: List[str] = []
        self.tokenized_corpus: List[List[str]] = []
        self.bm25: Optional[BM25Okapi] = None
        self.doc_vecs: Optional[np.ndarray] = None
        self.is_indexed: bool = False

    def _init_semantic_backend(self) -> None:
        if SentenceTransformer is not None:
            try:
                self.semantic_backend = SentenceTransformer(self.model_name)
                self.semantic_backend_name = f"sentence_transformer:{self.model_name}"
                return
            except Exception:
                pass

        self.semantic_backend = _SklearnSemanticEncoder()
        self.semantic_backend_name = "sklearn_tfidf_fallback"

    def index(self, chunks: List[Chunk]) -> None:
        if not chunks:
            self.chunks = []
            self.chunk_texts = []
            self.tokenized_corpus = []
            self.bm25 = None
            self.doc_vecs = None
            self.is_indexed = False
            return

        self.chunks = chunks
        self.chunk_texts = [chunk.text for chunk in chunks]
        self.tokenized_corpus = [_tokenize(text) for text in self.chunk_texts]
        self.bm25 = BM25Okapi(self.tokenized_corpus)

        if self.semantic_backend_name.startswith("sentence_transformer"):
            self.doc_vecs = self.semantic_backend.encode(
                self.chunk_texts,
                convert_to_numpy=True,
                normalize_embeddings=False,
            )
        else:
            self.doc_vecs = self.semantic_backend.fit(self.chunk_texts)

        self.is_indexed = True

    def _encode_query(self, query: str) -> np.ndarray:
        if self.semantic_backend_name.startswith("sentence_transformer"):
            return self.semantic_backend.encode(
                query,
                convert_to_numpy=True,
                normalize_embeddings=False,
            )
        return self.semantic_backend.encode_query(query)

    def _base_scores(self, query: str):
        query_terms = _query_terms(query)

        tokenized_query = _tokenize(query)
        bm25_scores = self.bm25.get_scores(tokenized_query).tolist()
        bm25_scores_norm = _min_max_normalize(bm25_scores)

        query_vec = self._encode_query(query)
        semantic_scores = _cosine_similarity_matrix(query_vec, self.doc_vecs).tolist()
        semantic_scores_norm = _min_max_normalize(semantic_scores)

        token_overlap_scores = [_token_overlap_boost(query_terms, chunk.text) for chunk in self.chunks]
        section_hint_scores = [_section_hint_boost(query_terms, chunk.section_hint) for chunk in self.chunks]
        phrase_scores = [_phrase_boost(query, chunk.text) for chunk in self.chunks]
        page_scores = [_page_boost(query, chunk.page_num) for chunk in self.chunks]
        recital_scores = [_opening_recital_boost(query, chunk.text, chunk.page_num) for chunk in self.chunks]

        combined_scores = [
            self.bm25_weight * b
            + self.semantic_weight * s
            + self.token_overlap_weight * t
            + self.section_hint_weight * h
            + self.phrase_weight * p
            + self.page_weight * pg
            + self.recital_weight * rc
            for b, s, t, h, p, pg, rc in zip(
                bm25_scores_norm,
                semantic_scores_norm,
                token_overlap_scores,
                section_hint_scores,
                phrase_scores,
                page_scores,
                recital_scores,
            )
        ]

        return {
            "bm25_norm": bm25_scores_norm,
            "semantic_norm": semantic_scores_norm,
            "token_overlap": token_overlap_scores,
            "section_hint": section_hint_scores,
            "phrase": phrase_scores,
            "page": page_scores,
            "recital": recital_scores,
            "combined": combined_scores,
        }

    def _rerank_score(self, query: str, idx: int, scores) -> float:
        chunk = self.chunks[idx]
        text = chunk.text
        hint = chunk.section_hint

        score = 0.0

        score += 0.34 * scores["combined"][idx]
        score += 0.18 * scores["bm25_norm"][idx]
        score += 0.16 * scores["semantic_norm"][idx]
        score += 0.10 * scores["phrase"][idx]
        score += 0.08 * scores["token_overlap"][idx]
        score += 0.04 * scores["section_hint"][idx]
        score += 0.03 * scores["page"][idx]
        score += 0.03 * scores["recital"][idx]

        score += _legal_label_boost(query, hint, text)

        score -= _residual_penalty(text)
        score -= _tiny_chunk_penalty(text)

        return float(score)

    def _retrieve_semantic_only(self, query: str, top_k: int = 6) -> List[RetrievedChunk]:
        scores = self._base_scores(query)

        ranked = sorted(
            range(len(self.chunks)),
            key=lambda i: (
                scores["semantic_norm"][i],
                scores["phrase"][i],
                scores["token_overlap"][i],
                scores["section_hint"][i],
            ),
            reverse=True,
        )[:top_k]

        results: List[RetrievedChunk] = []
        for rank, idx in enumerate(ranked, start=1):
            results.append(
                RetrievedChunk(
                    chunk=self.chunks[idx],
                    rank=rank,
                    combined_score=float(scores["semantic_norm"][idx]),
                    bm25_score=float(scores["bm25_norm"][idx]),
                    semantic_score=float(scores["semantic_norm"][idx]),
                )
            )
        return results

    def _retrieve_bm25_only(self, query: str, top_k: int = 6) -> List[RetrievedChunk]:
        scores = self._base_scores(query)

        ranked = sorted(
            range(len(self.chunks)),
            key=lambda i: (
                scores["bm25_norm"][i],
                scores["phrase"][i],
                scores["token_overlap"][i],
                scores["section_hint"][i],
            ),
            reverse=True,
        )[:top_k]

        results: List[RetrievedChunk] = []
        for rank, idx in enumerate(ranked, start=1):
            results.append(
                RetrievedChunk(
                    chunk=self.chunks[idx],
                    rank=rank,
                    combined_score=float(scores["bm25_norm"][idx]),
                    bm25_score=float(scores["bm25_norm"][idx]),
                    semantic_score=float(scores["semantic_norm"][idx]),
                )
            )
        return results

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
    ) -> List[RetrievedChunk]:
        if not query or not query.strip():
            raise ValueError("query must be non-empty")

        if not self.is_indexed or not self.chunks or self.bm25 is None or self.doc_vecs is None:
            return []

        if _is_party_query(query):
            top_k = max(top_k, 8)

        top_k = max(1, min(top_k, len(self.chunks)))
        scores = self._base_scores(query)

        bm25_ranked = sorted(
            range(len(self.chunks)),
            key=lambda i: scores["bm25_norm"][i],
            reverse=True,
        )

        semantic_ranked = sorted(
            range(len(self.chunks)),
            key=lambda i: scores["semantic_norm"][i],
            reverse=True,
        )

        pool_size = min(len(self.chunks), max(self.rerank_pool_size, top_k * 4))

        candidate_indices = set(bm25_ranked[:pool_size]) | set(semantic_ranked[:pool_size])

        reranked = sorted(
            candidate_indices,
            key=lambda i: self._rerank_score(query, i, scores),
            reverse=True,
        )[:top_k]

        results: List[RetrievedChunk] = []
        for rank, idx in enumerate(reranked, start=1):
            results.append(
                RetrievedChunk(
                    chunk=self.chunks[idx],
                    rank=rank,
                    combined_score=float(self._rerank_score(query, idx, scores)),
                    bm25_score=float(scores["bm25_norm"][idx]),
                    semantic_score=float(scores["semantic_norm"][idx]),
                )
            )

        return results

    def debug_scores(self, query: str):
        if not query or not query.strip():
            raise ValueError("query must be non-empty")

        if not self.is_indexed or not self.chunks or self.bm25 is None or self.doc_vecs is None:
            return []

        scores = self._base_scores(query)

        rows = []
        for i, chunk in enumerate(self.chunks):
            rows.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "page_num": chunk.page_num,
                    "section_hint": chunk.section_hint,
                    "bm25_score": float(scores["bm25_norm"][i]),
                    "semantic_score": float(scores["semantic_norm"][i]),
                    "token_overlap_score": float(scores["token_overlap"][i]),
                    "section_hint_score": float(scores["section_hint"][i]),
                    "phrase_score": float(scores["phrase"][i]),
                    "page_score": float(scores["page"][i]),
                    "recital_score": float(scores["recital"][i]),
                    "rerank_score": float(self._rerank_score(query, i, scores)),
                    "is_residual_junk": _is_residual_or_junk_chunk(chunk.text),
                    "semantic_backend": self.semantic_backend_name,
                    "text": chunk.text,
                }
            )

        return rows