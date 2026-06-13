from __future__ import annotations

import os
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException

from .models import OptimizeRequest, OptimizeResponse
from .optimizer import optimize


app = FastAPI(title="Gridwise Optimizer", version="0.1.0")


def verify_api_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
    expected_api_key = os.getenv("OPTIMISER_API_KEY")
    if expected_api_key and x_api_key != expected_api_key:
        raise HTTPException(status_code=401, detail="invalid API key")


@app.get("/health")
@app.get("/healthz")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/optimize", response_model=OptimizeResponse, dependencies=[Depends(verify_api_key)])
@app.post("/optimise", response_model=OptimizeResponse, dependencies=[Depends(verify_api_key)])
def optimize_endpoint(request: OptimizeRequest) -> OptimizeResponse:
    return optimize(request)
