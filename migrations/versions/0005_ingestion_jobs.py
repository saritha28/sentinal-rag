"""Ingestion jobs.

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-26

Implements Enterprise_RAG_Database_Design.md section 6 with the addition of
``workflow_id`` (text) tying each job to its Temporal workflow execution
(per ADR-0007).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE ingestion_jobs (
            id                   UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
            tenant_id            UUID         NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            collection_id        UUID         NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
            status               TEXT         NOT NULL DEFAULT 'queued'
                CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled')),
            input_source         JSONB        NOT NULL,
            chunking_strategy    TEXT         NOT NULL DEFAULT 'semantic',
            embedding_model      TEXT         NOT NULL,
            documents_total      INT          NOT NULL DEFAULT 0,
            documents_processed  INT          NOT NULL DEFAULT 0,
            chunks_created       INT          NOT NULL DEFAULT 0,
            error_message        TEXT,
            workflow_id          TEXT,
            started_at           TIMESTAMPTZ,
            completed_at         TIMESTAMPTZ,
            created_by           UUID         REFERENCES users(id),
            created_at           TIMESTAMPTZ  NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        "CREATE INDEX idx_ingestion_jobs_tenant_status "
        "ON ingestion_jobs(tenant_id, status)"
    )
    op.execute(
        "CREATE UNIQUE INDEX idx_ingestion_jobs_workflow_id "
        "ON ingestion_jobs(workflow_id) WHERE workflow_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ingestion_jobs CASCADE")
