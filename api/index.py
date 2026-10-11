"""Vercel entry point: exposes the FastAPI application (API + /app/ interface).

Vercel rewrites every route to this function and gives it "/api/index" as
its path; the original path arrives in the `__path` parameter (see
vercel.json). It is put back into the ASGI scope before calling FastAPI.
"""
import os
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("FIREBREAK_DEMO", "1")   # simulated AI, no external network

from firebreak.api import app as _fastapi  # noqa: E402


async def app(scope, receive, send):
    if scope["type"] == "http":
        qs = parse_qsl((scope.get("query_string") or b"").decode(), keep_blank_values=True)
        orig = next((v for k, v in qs if k == "__path"), None)
        if orig is not None:
            scope = dict(scope)
            path = orig or "/"
            if path.rstrip("/") == "/app":          # interface root → index.html
                path = "/app/index.html"
            scope["path"] = path
            scope["raw_path"] = path.encode()
            # Vercel also adds `path=<segments>` (group name): remove it.
            scope["query_string"] = urlencode(
                [(k, v) for k, v in qs if k not in ("__path", "path")]).encode()
    await _fastapi(scope, receive, send)
