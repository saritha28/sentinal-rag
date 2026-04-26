"""Bootstrap extensions and helper functions.

Revision ID: 0001
Revises:
Create Date: 2026-04-26
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Required extensions per Enterprise_RAG_Database_Design.md §2.
    # The local docker-compose volume init script also creates these, but the
    # migration is the source of truth in cloud environments where init scripts
    # don't run.
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # Helper: updated_at trigger function used across many tables.
    op.execute("""
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)


def downgrade() -> None:
    # Extensions are intentionally NOT dropped on downgrade — other databases
    # in the same cluster may rely on them, and dropping vector/pgcrypto would
    # cascade-destroy data. Keep them in place; only drop the helper function.
    op.execute("DROP FUNCTION IF EXISTS set_updated_at() CASCADE")
