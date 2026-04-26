"""Request-context middleware: assigns request_id, binds it to logs.

Every request gets a request_id (from ``X-Request-Id`` header if provided,
otherwise generated). It's:
    - Stored in the ``current_request_id`` contextvar so structlog adds it
      to every log line.
    - Echoed in the response header so callers can correlate.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.db.session import current_request_id


class RequestContextMiddleware(BaseHTTPMiddleware):
    HEADER = "X-Request-Id"

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        rid = request.headers.get(self.HEADER) or f"req_{uuid.uuid4().hex[:16]}"
        token = current_request_id.set(rid)
        structlog.contextvars.bind_contextvars(request_id=rid)

        try:
            response = await call_next(request)
        finally:
            current_request_id.reset(token)
            structlog.contextvars.unbind_contextvars("request_id")

        response.headers[self.HEADER] = rid
        return response
