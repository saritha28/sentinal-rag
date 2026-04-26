"""Structured logging for SentinelRAG services.

Single entry point: :func:`configure_logging`. Call once at process startup.
Emits JSON to stdout, includes OpenTelemetry trace/span IDs when available,
and respects the standard ``LOG_LEVEL`` environment variable.
"""

from sentinelrag_shared.logging.setup import configure_logging, get_logger

__all__ = ["configure_logging", "get_logger"]
