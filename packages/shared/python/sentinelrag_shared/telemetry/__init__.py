"""OpenTelemetry bootstrap for SentinelRAG services.

Single entry point: :func:`configure_telemetry`. Call once at process startup,
typically before instantiating the FastAPI app.
"""

from sentinelrag_shared.telemetry.setup import configure_telemetry

__all__ = ["configure_telemetry"]
