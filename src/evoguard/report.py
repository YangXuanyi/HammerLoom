from __future__ import annotations

import csv
import json
from html import escape
from pathlib import Path
from typing import Any, Dict

from .service import EvoGuard


def export_report(guard: EvoGuard, output_dir: str) -> Dict[str, str]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    data = guard.dashboard()
    json_path = target / "evolution-report.json"
    csv_path = target / "runs.csv"
    html_path = target / "evolution-report.html"
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["id", "task_id", "task_title", "agent_version", "success", "tokens", "duration_ms", "summary"])
        writer.writeheader()
        for run in data["runs"]:
            writer.writerow({field: run.get(field, "") for field in writer.fieldnames})
    summary = data["summary"]
    decision_rows = "".join(
        f"<tr><td>{escape(item['candidate_id'])}</td><td>{escape(item['verdict'])}</td><td>{escape('; '.join(item['reasons']))}</td></tr>"
        for item in data["decisions"]
    ) or "<tr><td colspan='3'>No decisions recorded.</td></tr>"
    html_path.write_text(
        "<!doctype html><html><head><meta charset='utf-8'><title>EvoGuard Report</title>"
        "<style>body{font:15px system-ui;margin:48px;color:#15202b}table{border-collapse:collapse;width:100%}th,td{padding:10px;border-bottom:1px solid #d8e0e4;text-align:left}h1{color:#0b655f}.stat{display:inline-block;margin-right:38px}</style>"
        "</head><body><h1>EvoGuard evolution report</h1>"
        f"<p class='stat'>Active policy: <b>{escape(summary['active_version'])}</b></p><p class='stat'>Run success: <b>{summary['success_rate']:.0%}</b></p><p class='stat'>Active Skills: <b>{summary['skills']}</b></p>"
        "<h2>Promotion decisions</h2><table><thead><tr><th>Candidate</th><th>Verdict</th><th>Evidence</th></tr></thead><tbody>"
        f"{decision_rows}</tbody></table></body></html>", encoding="utf-8")
    return {"json": str(json_path), "csv": str(csv_path), "html": str(html_path)}
