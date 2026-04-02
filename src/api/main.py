"""Fantasy Matchup Predictor — FastAPI application."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers import elo, talent, matchup, fantasy, export

app = FastAPI(title="Fantasy Matchup Predictor", version="1.0.0")

origins = [
    "http://localhost:5173",
    "http://localhost:3000",
]
if frontend_url := os.environ.get("FRONTEND_URL"):
    origins.append(frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(elo.router, prefix="/api/elo", tags=["elo"])
app.include_router(talent.router, prefix="/api/talent", tags=["talent"])
app.include_router(matchup.router, prefix="/api/matchup", tags=["matchup"])
app.include_router(fantasy.router, prefix="/api/fantasy", tags=["fantasy"])
app.include_router(export.router, prefix="/api/fantasy/export", tags=["export"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}
