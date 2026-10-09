"""
Tracks the number of HTTP requests currently in-flight on this uvicorn worker.

Used by /health/backlog to expose per-pod queue depth.
"""

import os
from typing import Any, Optional

from starlette.types import ASGIApp, Receive, Scope, Send


class InFlightRequestsMiddleware:
    """
    ASGI middleware that increments a counter when a request arrives and
    decrements it when the response is sent (or an error occurs).

    The counter is class-level and therefore scoped to a single uvicorn worker
    process — exactly the per-pod granularity we want.

    """

    _in_flight: int = 0

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        InFlightRequestsMiddleware._in_flight += 1
        try:
            await self.app(scope, receive, send)
        finally:
            InFlightRequestsMiddleware._in_flight -= 1

    @staticmethod
    def get_count() -> int:
        """Return the number of HTTP requests currently in-flight."""
        return InFlightRequestsMiddleware._in_flight

def get_in_flight_requests() -> int:
    """Module-level convenience wrapper used by the /health/backlog endpoint."""
    return InFlightRequestsMiddleware.get_count()
