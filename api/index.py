"""Point d'entrée Vercel : expose l'application FastAPI (API + interface /app/).

Vercel réécrit toutes les routes vers cette fonction et lui donne « /api/index »
comme chemin ; le chemin d'origine arrive dans le paramètre `__path`
(voir vercel.json). On le remet dans le scope ASGI avant d'appeler FastAPI.
"""
import os
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("FIREBREAK_DEMO", "1")   # IA simulée, pas de réseau externe

from firebreak.api import app as _fastapi  # noqa: E402


async def app(scope, receive, send):
    if scope["type"] == "http":
        qs = parse_qsl((scope.get("query_string") or b"").decode(), keep_blank_values=True)
        orig = next((v for k, v in qs if k == "__path"), None)
        if orig is not None:
            scope = dict(scope)
            path = orig or "/"
            if path.rstrip("/") == "/app":          # racine de l'interface → index.html
                path = "/app/index.html"
            scope["path"] = path
            scope["raw_path"] = path.encode()
            # Vercel ajoute aussi `path=<segments>` (nom du groupe) : on l'enlève.
            scope["query_string"] = urlencode(
                [(k, v) for k, v in qs if k not in ("__path", "path")]).encode()
    await _fastapi(scope, receive, send)
