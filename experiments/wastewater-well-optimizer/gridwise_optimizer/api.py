from __future__ import annotations

from fastapi import FastAPI

from .models import OptimizeRequest, OptimizeResponse
from .optimizer import optimize


app = FastAPI(title="Gridwise Optimizer", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/optimize", response_model=OptimizeResponse)
def optimize_endpoint(request: OptimizeRequest) -> OptimizeResponse:
    return optimize(request)

