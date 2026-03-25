"""Fantasy Matchup Predictor — FastAPI application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers import elo, talent, matchup, fantasy

app = FastAPI(title="Fantasy Matchup Predictor", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(elo.router, prefix="/api/elo", tags=["elo"])
app.include_router(talent.router, prefix="/api/talent", tags=["talent"])
app.include_router(matchup.router, prefix="/api/matchup", tags=["matchup"])
app.include_router(fantasy.router, prefix="/api/fantasy", tags=["fantasy"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}
