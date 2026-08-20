from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from .compiler import ExperienceCompiler
from .gate import PromotionGate
from .models import Candidate, PolicyVersion, PromotionDecision, Run, TraceEvent, new_id, now
from .store import Store


class RunRecorder:
    def __init__(self, guard: "EvoGuard", run: Run):
        self.guard = guard
        self.run = run

    @property
    def id(self) -> str:
        return self.run.id

    def event(self, kind: str, name: str, input: str = "", output: str = "", duration_ms: int = 0, **attributes: Any) -> None:
        self.run.events.append(TraceEvent(kind, name, duration_ms=duration_ms, input=input, output=output, attributes=attributes))
        self.run.duration_ms += duration_ms
        self.guard._save_run(self.run)

    def tool(self, name: str, input: str, output: str = "", duration_ms: int = 0, **attributes: Any) -> None:
        self.event("tool", name, input, output, duration_ms, **attributes)

    def model(self, name: str, input: str = "", output: str = "", tokens: int = 0, duration_ms: int = 0) -> None:
        self.run.tokens += tokens
        self.event("model", name, input, output, duration_ms, tokens=tokens)

    def diff(self, path: str, patch: str) -> None:
        self.run.changed_files.append({"path": path, "patch": patch})
        self.event("diff", path, output=patch)

    def verification(self, command: str, passed: bool, output: str = "", duration_ms: int = 0) -> None:
        self.run.verifier = command
        self.event("verification", command, output=output, duration_ms=duration_ms, passed=passed)

    def finish(self, success: bool, summary: str = "") -> Run:
        self.run.success = success
        self.run.summary = summary
        self.run.status = "completed"
        self.run.finished_at = now()
        self.guard._save_run(self.run)
        return self.run


class EvoGuard:
    def __init__(self, database_path: str = ".evoguard/evoguard.db", repo_scope: str = "repo:local"):
        self.store = Store(database_path)
        self.repo_scope = repo_scope
        self.compiler = ExperienceCompiler()
        self.gate = PromotionGate()
        if not self.store.all("versions"):
            initial = PolicyVersion(id="v0", parent_id=None, skill_ids=[], routing_rules=[])
            self.store.put("versions", initial.to_dict())

    def _save_run(self, run: Run) -> None:
        self.store.put("runs", run.to_dict())

    def active_version(self) -> Dict[str, Any]:
        versions = self.store.all("versions")
        active = [version for version in versions if version.get("state") == "active"]
        return active[-1] if active else self.store.get("versions", "v0")

    def start_run(self, task_id: str, task_title: str, task_cluster: str = "general") -> RunRecorder:
        run = Run(id=new_id("run"), task_id=task_id, task_title=task_title, task_cluster=task_cluster, agent_version=self.active_version()["id"])
        self._save_run(run)
        return RunRecorder(self, run)

    def compile_latest(self, run_id: str) -> Candidate:
        data = self.store.get("runs", run_id)
        if not data:
            raise KeyError(f"run not found: {run_id}")
        run = Run(**{**data, "events": [TraceEvent(**event) for event in data["events"]]})
        skill, candidate = self.compiler.compile(run, self.repo_scope)
        candidate.base_version = self.active_version()["id"]
        self.store.put("skills", skill.to_dict())
        self.store.put("candidates", candidate.to_dict())
        return candidate

    def evaluate(self, candidate_id: str, results: Optional[Dict[str, Any]] = None) -> PromotionDecision:
        candidate = self.store.get("candidates", candidate_id)
        if not candidate:
            raise KeyError(f"candidate not found: {candidate_id}")
        results = results or {"current_success": 0.90, "regression_drop": 0.02, "ood_success": 0.76, "token_delta": 0.08, "safety_violations": 0}
        verdict, metrics, reasons = self.gate.evaluate(results)
        version_id = None
        if verdict == "promoted":
            base = self.store.get("versions", candidate["base_version"])
            for version in self.store.all("versions"):
                if version["state"] == "active":
                    version["state"] = "archived"
                    self.store.put("versions", version)
            skill_ids = list(base["skill_ids"])
            for operation in candidate["operations"]:
                skill = operation.get("skill")
                if operation.get("op") == "ADD" and skill:
                    skill_ids.append(skill["id"])
                    skill["status"] = "active"
                    self.store.put("skills", skill)
            version_id = f"v{len(self.store.all('versions'))}"
            self.store.put("versions", PolicyVersion(id=version_id, parent_id=base["id"], skill_ids=skill_ids, routing_rules=base["routing_rules"], source_candidate_id=candidate_id).to_dict())
        candidate["status"] = verdict
        self.store.put("candidates", candidate)
        decision = PromotionDecision(id=new_id("decision"), candidate_id=candidate_id, verdict=verdict, metrics=metrics, reasons=reasons, promoted_version=version_id)
        self.store.put("decisions", decision.to_dict())
        return decision

    def rollback(self, version_id: str) -> Dict[str, Any]:
        target = self.store.get("versions", version_id)
        if not target:
            raise KeyError(f"version not found: {version_id}")
        for version in self.store.all("versions"):
            version["state"] = "active" if version["id"] == version_id else "archived"
            self.store.put("versions", version)
        return self.store.get("versions", version_id) or target

    def dashboard(self) -> Dict[str, Any]:
        runs = sorted(self.store.all("runs"), key=lambda item: item["created_at"])
        decisions = sorted(self.store.all("decisions"), key=lambda item: item["created_at"])
        completed = [run for run in runs if run["status"] == "completed"]
        success_rate = sum(1 for run in completed if run["success"]) / len(completed) if completed else 0
        return {
            "summary": {"runs": len(runs), "success_rate": round(success_rate, 2), "active_version": self.active_version()["id"], "skills": len([skill for skill in self.store.all("skills") if skill["status"] == "active"]), "safety_events": 0},
            "runs": runs,
            "versions": sorted(self.store.all("versions"), key=lambda item: item["created_at"]),
            "skills": self.store.all("skills"),
            "candidates": self.store.all("candidates"),
            "decisions": decisions,
        }

    def close(self) -> None:
        self.store.close()
