"""Reranker protocol + bge-reranker-v2-m3 implementation.

Per ADR-0006, the default reranker is BAAI's ``bge-reranker-v2-m3`` — open-source,
multilingual, and competitive with Cohere Rerank 3 on retrieval benchmarks.

Adapters:
    - ``BgeReranker`` — local model via FlagEmbedding's FlagReranker. CPU-mode
      acceptable for v1 demo; GPU node pool is the Phase-7 deployment story.
    - ``NoOpReranker`` — pass-through; used in tests and as a degraded fallback.
    - ``CohereReranker`` — env-flag opt-in (Phase 4+ work, not implemented here).

Model load is lazy + thread-safe; the first call pays the ~3-second model-load
cost. Subsequent calls reuse the in-memory model.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from sentinelrag_shared.llm.types import RerankResult, UsageRecord


class RerankerError(Exception):
    """Raised when reranking fails irrecoverably."""


@dataclass(slots=True)
class RerankCandidate:
    """Lightweight wrapper passed to the reranker.

    The reranker only needs the textual content + a stable identifier (for
    mapping rerank scores back to source chunks). The full Chunk object lives
    upstream; we keep this small to avoid copying around large metadata.
    """

    chunk_id: str
    text: str


class Reranker(Protocol):
    """Score (query, candidate) pairs and return candidates ordered by relevance."""

    model_name: str

    def rerank(
        self,
        *,
        query: str,
        candidates: Sequence[RerankCandidate],
        top_k: int,
    ) -> RerankResult: ...


class NoOpReranker:
    """Pass-through; preserves input order, returns top_k.

    Useful for unit tests where we want to exercise the rest of the pipeline
    without paying the model-load cost, AND as a graceful fallback if the
    real reranker fails to load (the orchestrator can opt to degrade to this).
    """

    model_name = "noop"

    def rerank(
        self,
        *,
        query: str,
        candidates: Sequence[RerankCandidate],
        top_k: int,
    ) -> RerankResult:
        del query
        n = min(top_k, len(candidates))
        return RerankResult(
            indices=list(range(n)),
            scores=[1.0 - i * 0.01 for i in range(n)],  # monotonically decreasing
            model_name=self.model_name,
            usage=UsageRecord(usage_type="rerank", provider="local", model_name=self.model_name),
        )


# Module-level cache so multiple BgeReranker instances share one loaded model.
_BGE_LOCK = threading.Lock()
_BGE_MODEL: Any | None = None
_BGE_MODEL_NAME: str | None = None


class BgeReranker:
    """Cross-encoder reranker using ``BAAI/bge-reranker-v2-m3`` by default.

    Uses ``FlagEmbedding.FlagReranker`` if available, falling back to
    ``sentence_transformers.CrossEncoder`` if not. Both expose a ``compute_score``
    or ``predict`` method that takes ``(query, passage)`` pairs.
    """

    def __init__(
        self,
        *,
        model_name: str = "BAAI/bge-reranker-v2-m3",
        use_fp16: bool = True,
        max_length: int = 512,
        batch_size: int = 32,
    ) -> None:
        self.model_name = model_name
        self._use_fp16 = use_fp16
        self._max_length = max_length
        self._batch_size = batch_size

    def _ensure_model(self) -> Any:
        """Lazy load with thread-safe cache."""
        global _BGE_MODEL, _BGE_MODEL_NAME  # noqa: PLW0603
        if _BGE_MODEL is not None and self.model_name == _BGE_MODEL_NAME:
            return _BGE_MODEL
        with _BGE_LOCK:
            if _BGE_MODEL is not None and self.model_name == _BGE_MODEL_NAME:
                return _BGE_MODEL
            try:
                from FlagEmbedding import FlagReranker  # noqa: PLC0415
            except ImportError:
                FlagReranker = None  # type: ignore[assignment]  # noqa: N806 — sentinel for the imported class

            if FlagReranker is not None:
                try:
                    _BGE_MODEL = FlagReranker(self.model_name, use_fp16=self._use_fp16)
                    _BGE_MODEL_NAME = self.model_name
                    return _BGE_MODEL
                except Exception as exc:
                    msg = f"FlagReranker failed to load {self.model_name}: {exc}"
                    raise RerankerError(msg) from exc

            # Fallback to sentence-transformers CrossEncoder.
            try:
                from sentence_transformers import CrossEncoder  # noqa: PLC0415

                _BGE_MODEL = CrossEncoder(self.model_name, max_length=self._max_length)
                _BGE_MODEL_NAME = self.model_name
                return _BGE_MODEL
            except Exception as exc:
                msg = (
                    f"Neither FlagEmbedding nor sentence-transformers could load "
                    f"{self.model_name!r}: {exc}"
                )
                raise RerankerError(msg) from exc

    def rerank(
        self,
        *,
        query: str,
        candidates: Sequence[RerankCandidate],
        top_k: int,
    ) -> RerankResult:
        if not candidates:
            return RerankResult(
                indices=[],
                scores=[],
                model_name=self.model_name,
                usage=UsageRecord(
                    usage_type="rerank", provider="local", model_name=self.model_name
                ),
            )

        model = self._ensure_model()
        pairs = [(query, c.text) for c in candidates]

        start = time.perf_counter()
        scores = self._score(model, pairs)
        latency_ms = int((time.perf_counter() - start) * 1000)

        indexed = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        kept = indexed[: max(top_k, 0)]
        out_indices = [i for i, _ in kept]
        out_scores = [float(s) for _, s in kept]

        return RerankResult(
            indices=out_indices,
            scores=out_scores,
            model_name=self.model_name,
            usage=UsageRecord(
                usage_type="rerank",
                provider="local",
                model_name=self.model_name,
                latency_ms=latency_ms,
            ),
        )

    def _score(self, model: Any, pairs: list[tuple[str, str]]) -> list[float]:
        """Dispatch on the loaded model's API surface."""
        # FlagReranker uses ``compute_score(pairs, normalize=True)``.
        if hasattr(model, "compute_score"):
            raw = model.compute_score(pairs, normalize=True, batch_size=self._batch_size)
            if isinstance(raw, list):
                return [float(s) for s in raw]
            return [float(raw)]
        # CrossEncoder uses ``predict(pairs, batch_size=...)``.
        if hasattr(model, "predict"):
            raw = model.predict(pairs, batch_size=self._batch_size, show_progress_bar=False)
            return [float(s) for s in raw]
        msg = "Loaded model has neither compute_score nor predict."
        raise RerankerError(msg)
