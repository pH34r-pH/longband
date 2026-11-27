"""Request-size limit for the public Alpha service.

Declared (Content-Length) and streamed bodies are capped before the application parses
them, so an unauthenticated caller cannot make the process buffer arbitrarily large JSON.
"""

from __future__ import annotations

import json

MAX_BODY_BYTES = 524_288

_TOO_LARGE = json.dumps({"detail": "Request too large"}).encode()
_HEADERS = [(b"content-type", b"application/json"), (b"content-length", str(len(_TOO_LARGE)).encode())]


class _Exceeded(Exception):
    pass


class BodyLimit:
    def __init__(self, app, max_bytes: int = MAX_BODY_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        for name, value in scope["headers"]:
            if name == b"content-length":
                try:
                    declared = int(value)
                except ValueError:
                    declared = self.max_bytes + 1
                if declared > self.max_bytes:
                    await self._reject(send)
                    return
        received = 0
        exceeded = False
        responded = False

        async def limited_receive():
            nonlocal received, exceeded
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    exceeded = True
                    raise _Exceeded
            return message

        async def guarded_send(message):
            nonlocal responded
            if exceeded:
                # The application failed while reading an oversized stream: report that instead.
                if not responded:
                    responded = True
                    await self._reject(send)
                return
            await send(message)

        try:
            await self.app(scope, limited_receive, guarded_send)
        except _Exceeded:
            pass
        if exceeded and not responded:
            await self._reject(send)

    @staticmethod
    async def _reject(send):
        await send({"type": "http.response.start", "status": 413, "headers": _HEADERS})
        await send({"type": "http.response.body", "body": _TOO_LARGE})
