"""Candidate — the unit of retrieval output."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID


class RetrievalStage(StrEnum):
    """Pipeline stage that produced a Candidate.

    Mirrors the ``retrieval_stage`` CHECK constraint on ``retrieval_results``.
    """

    BM25 = "bm25"
    VECTOR = "vector"
    HYBRID_MERGE = "hybrid_merge"
    RERANK = "rerank"


@dataclass(slots=True)
class Candidate:
    """A retrieval result, decoupled from any DB row.

    The same Candidate flows through BM25 → Vector → Merge → Rerank, with each
    stage producing a new Candidate (or augmenting the existing one's metadata).
    """

    chunk_id: UUID
    document_id: UUID
    content: str
    score: float
    rank: int
    stage: RetrievalStage
    page_number: int | None = None
    section_title: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
