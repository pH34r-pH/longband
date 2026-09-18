from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.routing import Mount

from .http import app as http_app
from .mcp_server import mcp


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp.session_manager.run():
        yield


app = FastAPI(title="Longband Alpha service", lifespan=lifespan)
app.mount("/mcp", mcp.streamable_http_app())
app.mount("/", http_app)
