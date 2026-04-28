"""KeywordSearch protocol + Postgres FTS implementation (ADR-0004).

The Postgres FTS path uses the ``content_tsv`` column (GENERATED ALWAYS
from ``content``) with the ``idx_chunks_content_tsv`` GIN index.

Scoring uses ``ts_rank_cd`` with default normalization. This is BM25-shaped
but not pure BM25 — that's an intentional v1 trade-off (ADR-0004); a Phase-8
OpenSearch adapter will plug in behind the same protocol when the migration
case becomes worth telling.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelrag_shared.auth import AuthContext
from sentinelrag_shared.retrieval.access_filter import AccessFilter
from sentinelrag_shared.retrieval.candidate import Candidate, RetrievalStage


class KeywordSearch(Protocol):
    """Protocol for BM25-style keyword retrieval."""

    async def search(
        self,
        *,
        query: str,
        auth: AuthContext,
        collection_ids: list[UUID] | None,
        top_k: int,
    ) -> list[Candidate]: ...


class PostgresFtsKeywordSearch:
    """Postgres FTS-backed keyword search.

    Args:
        session: AsyncSession bound to the tenant context (RLS-enabled).
        access_filter: pre-built AccessFilter; sharing the instance across
            multiple search calls is safe.
        ts_config: Postgres text-search configuration (default ``english``).
            Must match the configuration used in the GENERATED ``content_tsv``
            column expression — they're set in 0004_documents migration.
    """

    def __init__(
        self,
        *,
        session: AsyncSession,
        access_filter: AccessFilter | None = None,
        ts_config: str = "english",
    ) -> None:
        self.session = session
        self.access_filter = access_filter or AccessFilter()
        self.ts_config = ts_config

    async def search(
        self,
        *,
        query: str,
        auth: AuthContext,
        collection_ids: list[UUID] | None,
        top_k: int,
    ) -> list[Candidate]:
        if not query.strip() or top_k <= 0:
            return []

        predicate = self.access_filter.build(auth=auth, collection_ids=collection_ids)

        # ``websearch_to_tsquery`` understands user-friendly syntax:
        # ``'kubernetes "rolling update" OR helm'`` parses correctly and
        # tolerates malformed input gracefully (returns empty tsquery).
        # S608: SQL is composed from internally-generated identifiers
        # (predicate.cte_sql, predicate.sql) — no user input is interpolated.
        sql = f"""
            {predicate.cte_sql}
            SELECT
                chunks.id,
                chunks.document_id,
                chunks.content,
                chunks.page_number,
                chunks.section_title,
                ts_rank_cd(chunks.content_tsv,
                           websearch_to_tsquery(:ts_config, :query)) AS score
            FROM document_chunks chunks
            WHERE chunks.content_tsv @@ websearch_to_tsquery(:ts_config, :query)
              AND {predicate.sql}
            ORDER BY score DESC
            LIMIT :top_k
        """  # noqa: S608

        result = await self.session.execute(
            text(sql),
            {
                **predicate.params,
                "ts_config": self.ts_config,
                "query": query,
                "top_k": top_k,
            },
        )
        rows = result.fetchall()

        return [
            Candidate(
                chunk_id=row.id,
                document_id=row.document_id,
                content=row.content,
                score=float(row.score or 0.0),
                rank=rank,
                stage=RetrievalStage.BM25,
                page_number=row.page_number,
                section_title=row.section_title,
            )
            for rank, row in enumerate(rows, start=1)
        ]
