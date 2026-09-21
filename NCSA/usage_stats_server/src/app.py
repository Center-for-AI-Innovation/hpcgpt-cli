from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from src.store import SessionStore


class SessionIngest(BaseModel):
    session_id: str = Field(..., min_length=1)
    username: str = Field(..., min_length=1)
    hostname: str = Field(..., min_length=1)
    started_at: str = Field(..., min_length=1)
    ended_at: str = Field(..., min_length=1)
    duration_sec: int = Field(..., ge=0)
    exit_code: int


def create_app(store: SessionStore) -> FastAPI:
    app = FastAPI(
        title="hpcGPT Usage Stats",
        description="Ingest and query hpc-gpt session usage statistics",
        version="1.0.0",
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/sessions")
    def ingest_session(body: SessionIngest) -> dict:
        try:
            record = store.insert_session(
                session_id=body.session_id,
                username=body.username,
                hostname=body.hostname,
                started_at=body.started_at,
                ended_at=body.ended_at,
                duration_sec=body.duration_sec,
                exit_code=body.exit_code,
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return {"ok": True, "session": record}

    @app.get("/v1/sessions")
    def list_sessions(
        username: Optional[str] = Query(default=None),
        limit: int = Query(default=100, ge=1, le=1000),
    ) -> dict:
        sessions = store.list_sessions(username=username, limit=limit)
        return {"count": len(sessions), "sessions": sessions}

    @app.get("/v1/stats")
    def stats() -> dict:
        return store.get_stats()

    return app
