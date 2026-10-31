"""Request correlation ids (N3).

Reads `X-Request-ID` from the incoming request or generates one, binds it so
every log line in the request carries it, and sets it on the response.

Written as **pure ASGI rather than `BaseHTTPMiddleware`** for one reason that
matters: it wraps `send`, so the header is attached to the response message
itself. That means it is present on responses this middleware never sees as
return values — 404s from the router, 422s from validation, and the 500 that
`ServerErrorMiddleware` builds after a handler raises. A `BaseHTTPMiddleware`
implementation would lose the header on exactly the responses you most want to
correlate with a log line.

The incoming header is **untrusted input**. It is echoed back and written into
every log line for the request, so a client could otherwise inject newlines or
control characters into the log stream, or pin thousands of requests to one id.
Anything that does not look like an id is replaced with a fresh one.
"""

from __future__ import annotations

import re

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import bind_request_id

REQUEST_ID_HEADER = "X-Request-ID"

# Long enough for a UUID or a trace id, short enough not to bloat a log line.
MAX_REQUEST_ID_LENGTH = 128

# Deliberately strict: the characters that appear in UUIDs, ULIDs, W3C trace
# ids and the usual load-balancer request ids, and nothing else.
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def sanitize_request_id(candidate: str | None) -> str | None:
    """Return the id if it is safe to echo and log, otherwise None."""
    if not candidate:
        return None
    candidate = candidate.strip()
    if len(candidate) > MAX_REQUEST_ID_LENGTH:
        return None
    if not _VALID_REQUEST_ID.match(candidate):
        return None
    return candidate


class RequestIdMiddleware:
    """Bind a request id for the duration of the request and echo it back."""

    def __init__(self, app: ASGIApp, header_name: str = REQUEST_ID_HEADER) -> None:
        self.app = app
        self.header_name = header_name

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # Lifespan and websocket scopes have no headers to read or set.
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = Headers(scope=scope).get(self.header_name)
        request_id = bind_request_id(sanitize_request_id(incoming))

        # Expose it to handlers as `request.state.request_id`.
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)[self.header_name] = request_id
            await send(message)

        await self.app(scope, receive, send_with_request_id)
