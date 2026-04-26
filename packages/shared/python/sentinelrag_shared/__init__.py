"""Shared cross-service utilities for SentinelRAG.

Submodules:
    logging       - structlog JSON setup with trace correlation.
    telemetry     - OpenTelemetry bootstrap (traces, metrics, logs).
    auth          - JWT verification, AuthContext, RBAC primitives.
    errors        - Standardized error response types.
    contracts     - Cross-service Pydantic request/response models.
    llm           - LiteLLM gateway adapter.
    feature_flags - Unleash client wrapper.
    object_storage - S3/GCS/Azure Blob/MinIO unified interface.
    secrets       - Secrets provider abstraction.
"""

__version__ = "0.1.0"
