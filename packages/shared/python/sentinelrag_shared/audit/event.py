"""AuditEvent — the unit of audit dual-write (ADR-0016).

Mirrors the ``audit_events`` table columns from migration 0009 plus a few
fields that only the S3 archive needs (the platform-issued event UUID is
generated client-side so the Postgres + S3 paths agree on identity even
when one path lags).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class AuditEvent(BaseModel):
    """One audit-relevant event, dual-written to Postgres + S3 Object Lock."""

    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    actor_user_id: UUID | None = None
    event_type: str  # e.g. "query.executed", "budget.denied"
    resource_type: str | None = None
    resource_id: UUID | None = None
    action: str  # "create" | "read" | "update" | "delete" | "execute"
    ip_address: str | None = None
    user_agent: str | None = None
    request_id: str | None = None
    before_state: dict[str, Any] | None = None
    after_state: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def s3_key(self) -> str:
        """Hierarchical key per ADR-0016 — partitions queryable via Athena."""
        d = self.created_at.astimezone(UTC)
        return (
            f"tenant_id={self.tenant_id}/"
            f"year={d.year:04d}/"
            f"month={d.month:02d}/"
            f"day={d.day:02d}/"
            f"hour={d.hour:02d}/"
            f"{self.id}.json.gz"
        )
