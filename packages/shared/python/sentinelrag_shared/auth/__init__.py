"""Auth primitives: AuthContext, JWT verification, RBAC guards.

The package intentionally has no FastAPI dependencies — the FastAPI binding
lives in the API service. Other services (retrieval, evaluation) import these
primitives and wire them into their own framework as needed.
"""

from sentinelrag_shared.auth.context import AuthContext
from sentinelrag_shared.auth.jwt import JWTVerifier, JWTVerifierError

__all__ = [
    "AuthContext",
    "JWTVerifier",
    "JWTVerifierError",
]
