"""
Tracks the number of HTTP requests currently in-flight on this uvicorn worker.
"""

from typing import Any

from starlette.types import ASGIApp, Receive, Scope, Send


class InFlightRequestsMiddleware:
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
        return InFlightRequestsMiddleware._in_flight

    @staticmethod
    def _get_gauge() -> Any | None:
        return None


def get_in_flight_requests() -> int:
    return InFlightRequestsMiddleware.get_count()
