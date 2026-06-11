"""Lambda entrypoint — adapts the FastAPI app to API Gateway via Mangum."""
from __future__ import annotations

from mangum import Mangum

from api.app import app

handler = Mangum(app, lifespan="off")
