"""Evaluation datasets, cases, runs, scores.

Revision ID: 0008
Revises: 0007
Create Date: 2026-04-26

Implements Enterprise_RAG_Database_Design.md sections 9.1-9.4.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE evaluation_datasets (
            id            UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
            tenant_id     UUID         NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name          TEXT         NOT NULL,
            description   TEXT,
            dataset_type  TEXT         NOT NULL DEFAULT 'golden'
                CHECK (dataset_type IN ('golden', 'regression', 'production_sample')),
            created_by    UUID         REFERENCES users(id),
            created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),

            UNIQUE (tenant_id, name)
        )
    """)

    op.execute("""
        CREATE TABLE evaluation_cases (
            id                            UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
            tenant_id                     UUID         NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            dataset_id                    UUID         NOT NULL REFERENCES evaluation_datasets(id) ON DELETE CASCADE,
            input_query                   TEXT         NOT NULL,
            expected_answer               TEXT,
            expected_citation_chunk_ids   UUID[]       NOT NULL DEFAULT '{}',
            grading_rubric                JSONB        NOT NULL DEFAULT '{}'::jsonb,
            metadata                      JSONB        NOT NULL DEFAULT '{}'::jsonb,
            created_at                    TIMESTAMPTZ  NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX idx_eval_cases_dataset ON evaluation_cases(dataset_id)")

    op.execute("""
        CREATE TABLE evaluation_runs (
            id                  UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
            tenant_id           UUID         NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            dataset_id          UUID         NOT NULL REFERENCES evaluation_datasets(id),
            name                TEXT         NOT NULL,
            model_config        JSONB        NOT NULL,
            retrieval_config    JSONB        NOT NULL,
            prompt_version_id   UUID         REFERENCES prompt_versions(id),
            workflow_id         TEXT,
            status              TEXT         NOT NULL DEFAULT 'queued'
                CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled')),
            started_at          TIMESTAMPTZ,
            completed_at        TIMESTAMPTZ,
            created_by          UUID         REFERENCES users(id),
            created_at          TIMESTAMPTZ  NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        "CREATE INDEX idx_evaluation_runs_dataset "
        "ON evaluation_runs(dataset_id, created_at DESC)"
    )

    op.execute("""
        CREATE TABLE evaluation_scores (
            id                         UUID              PRIMARY KEY DEFAULT uuid_generate_v4(),
            tenant_id                  UUID              NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            evaluation_run_id          UUID              NOT NULL REFERENCES evaluation_runs(id) ON DELETE CASCADE,
            evaluation_case_id         UUID              NOT NULL REFERENCES evaluation_cases(id) ON DELETE CASCADE,
            query_session_id           UUID              REFERENCES query_sessions(id),
            context_relevance_score    DOUBLE PRECISION,
            faithfulness_score         DOUBLE PRECISION,
            answer_correctness_score   DOUBLE PRECISION,
            citation_accuracy_score    DOUBLE PRECISION,
            latency_ms                 INT,
            cost_usd                   NUMERIC(12, 6),
            judge_model                TEXT,
            judge_reasoning            TEXT,
            created_at                 TIMESTAMPTZ       NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        "CREATE INDEX idx_eval_scores_run ON evaluation_scores(evaluation_run_id)"
    )
    op.execute(
        "CREATE INDEX idx_eval_scores_case ON evaluation_scores(evaluation_case_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS evaluation_scores CASCADE")
    op.execute("DROP TABLE IF EXISTS evaluation_runs CASCADE")
    op.execute("DROP TABLE IF EXISTS evaluation_cases CASCADE")
    op.execute("DROP TABLE IF EXISTS evaluation_datasets CASCADE")
