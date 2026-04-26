"""SQLAlchemy declarative base + common types.

All ORM models inherit from :class:`Base`. The base does NOT define a custom
metadata or naming convention beyond SQLAlchemy's defaults — Alembic
migrations are hand-written, so the metadata is not used for autogeneration
(see ``migrations/env.py``).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from sqlalchemy import TIMESTAMP, MetaData
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Application ORM base class."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# Reusable column annotations.
PrimaryKeyUUID = Annotated[
    UUID,
    mapped_column(PG_UUID(as_uuid=True), primary_key=True),
]

TenantIdFK = Annotated[
    UUID,
    mapped_column(PG_UUID(as_uuid=True), nullable=False),
]

TimestampTZ = Annotated[
    datetime,
    mapped_column(TIMESTAMP(timezone=True), nullable=False),
]
