from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from .service import EvoGuard


def create_app(database_path: str = ".evoguard/evoguard.db"):
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.responses import FileResponse
    except ImportError as exc:
        raise RuntimeError("Studio requires FastAPI and uvicorn. Run: python -m pip install -e .") from exc

    guard = EvoGuard(database_path)
    app = FastAPI(title="EvoGuard Studio", version="0.1.0")
    studio_dir = Path(__file__).parent / "studio"

    @app.get("/api/dashboard")
    def dashboard() -> Dict[str, Any]:
        return guard.dashboard()

    @app.get("/api/runs/{run_id}")
    def run(run_id: str) -> Dict[str, Any]:
        item = guard.store.get("runs", run_id)
        if not item:
            raise HTTPException(status_code=404, detail="未找到该运行记录")
        candidates = [
            candidate
            for candidate in guard.store.all("candidates")
            if run_id in candidate.get("evidence_run_ids", [])
        ]
        candidate_ids = {candidate["id"] for candidate in candidates}
        decisions = [
            decision
            for decision in guard.store.all("decisions")
            if decision.get("candidate_id") in candidate_ids
        ]
        skills = [
            skill
            for skill in guard.store.all("skills")
            if run_id in skill.get("evidence_run_ids", [])
        ]
        model_events = [event for event in item.get("events", []) if event.get("kind") == "model"]
        item["model_usage"] = {
            "calls": len(model_events),
            "tokens": sum(int(event.get("attributes", {}).get("tokens", 0)) for event in model_events),
            "duration_ms": sum(int(event.get("duration_ms", 0)) for event in model_events),
        }
        item["candidates"] = candidates
        item["decisions"] = decisions
        item["skills"] = skills
        return item

    @app.post("/api/versions/{version_id}/rollback")
    def rollback(version_id: str) -> Dict[str, Any]:
        try:
            return guard.rollback(version_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Version not found")

    @app.get("/")
    def studio() -> FileResponse:
        return FileResponse(studio_dir / "index.html", headers={"Cache-Control": "no-store"})

    @app.get("/app.js")
    def script() -> FileResponse:
        return FileResponse(
            studio_dir / "app.js",
            media_type="application/javascript",
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/styles.css")
    def styles() -> FileResponse:
        return FileResponse(
            studio_dir / "styles.css",
            media_type="text/css",
            headers={"Cache-Control": "no-store"},
        )

    return app
