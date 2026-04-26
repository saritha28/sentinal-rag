"""JWT verification with JWKS caching.

Verifies RS256-signed tokens issued by Keycloak. The JWKS endpoint is fetched
once and cached for ``jwks_cache_ttl_seconds`` (default 1 hour). When a token
references a ``kid`` not in the cache, we refetch immediately.

The verifier checks:
    - signature against the matching JWK
    - ``iss`` matches ``issuer``
    - ``aud`` matches ``audience``
    - ``exp`` and ``nbf``
    - presence of ``sub`` and our custom ``tenant_id`` claim
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import httpx
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError

DEFAULT_JWKS_TTL = 3600


class JWTVerifierError(Exception):
    """Raised when a JWT fails verification (signature, claims, format)."""


@dataclass(slots=True)
class _JwksCache:
    keys: dict[str, dict[str, Any]] = field(default_factory=dict)
    fetched_at: float = 0.0


@dataclass(slots=True)
class VerifiedClaims:
    sub: UUID
    tenant_id: UUID
    email: str
    raw: dict[str, Any]


class JWTVerifier:
    """JWKS-cached RS256 verifier for Keycloak tokens."""

    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        jwks_url: str,
        algorithms: tuple[str, ...] = ("RS256",),
        jwks_cache_ttl_seconds: int = DEFAULT_JWKS_TTL,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._issuer = issuer
        self._audience = audience
        self._jwks_url = jwks_url
        self._algorithms = list(algorithms)
        self._cache_ttl = jwks_cache_ttl_seconds
        self._cache = _JwksCache()
        self._http = http_client or httpx.AsyncClient(timeout=5.0)

    async def verify(self, token: str) -> VerifiedClaims:
        """Validate the token and return parsed claims, or raise ``JWTVerifierError``."""
        try:
            unverified_header = jwt.get_unverified_header(token)
        except JWTError as exc:
            msg = "Token header is malformed."
            raise JWTVerifierError(msg) from exc

        kid = unverified_header.get("kid")
        if not kid:
            msg = "Token header missing 'kid'."
            raise JWTVerifierError(msg)

        key = await self._get_key(kid)
        try:
            claims = jwt.decode(
                token,
                key,
                algorithms=self._algorithms,
                audience=self._audience,
                issuer=self._issuer,
            )
        except ExpiredSignatureError as exc:
            msg = "Token expired."
            raise JWTVerifierError(msg) from exc
        except JWTError as exc:
            msg = f"Token verification failed: {exc}"
            raise JWTVerifierError(msg) from exc

        return self._extract_claims(claims)

    @staticmethod
    def _extract_claims(claims: dict[str, Any]) -> VerifiedClaims:
        sub = claims.get("sub")
        tenant_id = claims.get("tenant_id")
        email = claims.get("email")
        if not sub:
            msg = "Token missing 'sub'."
            raise JWTVerifierError(msg)
        if not tenant_id:
            msg = "Token missing 'tenant_id' custom claim."
            raise JWTVerifierError(msg)
        if not email:
            msg = "Token missing 'email'."
            raise JWTVerifierError(msg)
        try:
            return VerifiedClaims(
                sub=UUID(sub),
                tenant_id=UUID(tenant_id),
                email=email,
                raw=claims,
            )
        except (ValueError, TypeError) as exc:
            msg = "Token 'sub' or 'tenant_id' is not a valid UUID."
            raise JWTVerifierError(msg) from exc

    async def _get_key(self, kid: str) -> dict[str, Any]:
        if self._is_cache_stale() or kid not in self._cache.keys:
            await self._refresh_jwks()
        if kid not in self._cache.keys:
            msg = f"No JWK matches kid={kid}."
            raise JWTVerifierError(msg)
        return self._cache.keys[kid]

    def _is_cache_stale(self) -> bool:
        return (time.time() - self._cache.fetched_at) > self._cache_ttl

    async def _refresh_jwks(self) -> None:
        try:
            response = await self._http.get(self._jwks_url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            msg = f"Failed to fetch JWKS from {self._jwks_url}: {exc}"
            raise JWTVerifierError(msg) from exc
        body = response.json()
        keys = body.get("keys", [])
        self._cache = _JwksCache(
            keys={k["kid"]: k for k in keys if "kid" in k},
            fetched_at=time.time(),
        )

    async def close(self) -> None:
        await self._http.aclose()
