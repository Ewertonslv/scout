"""Run the whole scout demo on a laptop — no AWS, no Bedrock, zero cost.

    python demo.py            # -> http://127.0.0.1:8000

It forces ``SCOUT_OFFLINE`` (deterministic stub model + in-memory job store),
then serves the bundled SPA and the API together so the frontend — which calls
``<origin>/api/*`` — works unmodified. Submit a topic and watch the five-agent
pipeline hand back a cited brief.

This is the demo path recruiters click; the same agents run on real Bedrock +
Step Functions once the SAM stack is deployed (see README).
"""
from __future__ import annotations

import os
import pathlib
import sys

os.environ.setdefault("SCOUT_OFFLINE", "1")

ROOT = pathlib.Path(__file__).parent.resolve()
sys.path.insert(0, str(ROOT / "src"))

import uvicorn  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from api.app import app as api_app  # noqa: E402

root = FastAPI(title="scout — local demo")
# Order matters: match /api/* before the catch-all static mount.
root.mount("/api", api_app)
root.mount("/", StaticFiles(directory=str(ROOT / "frontend"), html=True), name="frontend")


def main() -> None:
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    print(f"scout demo (offline, $0) -> http://{host}:{port}")
    uvicorn.run(root, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
