from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

from .api import create_app
from .demo import seed_demo
from .report import export_report
from .service import HammerLoom


def database_path(value: Optional[str]) -> str:
    return value or ".hammerloom/hammerloom.db"


def main() -> None:
    parser = argparse.ArgumentParser(prog="hammerloom", description="Evidence-driven evolution control plane for coding agents")
    parser.add_argument("--db", help="SQLite database path (default: .hammerloom/hammerloom.db)")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="Initialize local HammerLoom state")
    init.add_argument("--repo", default=".", help="Repository tracked by this local state")
    sub.add_parser("demo", help="Seed a deterministic completed evolution cycle")
    studio = sub.add_parser("studio", help="Run the local Evolution Studio")
    studio.add_argument("--host", default="127.0.0.1")
    studio.add_argument("--port", type=int, default=8765)
    report = sub.add_parser("report", help="Export JSON, CSV, and static HTML evidence report")
    report.add_argument("--output", default=".hammerloom/reports")
    args = parser.parse_args()
    db = database_path(args.db)

    if args.command == "init":
        scope = f"repo:{Path(args.repo).resolve()}"
        HammerLoom(db, repo_scope=scope)
        print(json.dumps({"database": db, "scope": scope, "active_version": "v0"}, ensure_ascii=False))
    elif args.command == "demo":
        print(seed_demo(HammerLoom(db)))
    elif args.command == "report":
        paths = export_report(HammerLoom(db), args.output)
        print(json.dumps(paths, ensure_ascii=False))
    elif args.command == "studio":
        try:
            import uvicorn
        except ImportError:
            parser.error("Studio needs FastAPI and uvicorn. Install project dependencies first.")
        uvicorn.run(create_app(db), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
