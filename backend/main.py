from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .core.database import init_db
from .routers import (
    investigations, findings, assets,
    notes, scope, timeline, reports,
    commit, settings, tintel, review
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(
    title="Argus",
    description="AI-Powered Pentester's Workstation — v0.0",
    version="0.0.1",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(investigations.router)
app.include_router(findings.router)
app.include_router(assets.router)
app.include_router(notes.router)
app.include_router(scope.router)
app.include_router(timeline.router)
app.include_router(reports.router)
app.include_router(commit.router)
app.include_router(settings.router)
app.include_router(tintel.router)
app.include_router(review.router)

@app.get("/")
async def root():
    return {"name": "Argus", "version": "0.0.1", "status": "running"}

@app.get("/health")
async def health():
    return {"status": "ok"}
