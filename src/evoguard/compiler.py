from __future__ import annotations

from typing import List

from .models import Candidate, Run, Skill, new_id


class ExperienceCompiler:
    """Produces small, attributable Skills from verified task evidence."""

    def compile(self, run: Run, scope: str) -> tuple[Skill, Candidate]:
        if not run.success or not run.verifier:
            raise ValueError("only successful runs with a verifier can produce a Skill candidate")

        tool_events = [event for event in run.events if event.kind == "tool"]
        procedure: List[str] = []
        for event in tool_events[:4]:
            command = event.input.strip().replace("\n", " ")
            if command:
                procedure.append(f"Run `{command[:140]}` and inspect the result.")
        if not procedure:
            procedure.append("Reproduce the verifier failure, identify the smallest relevant change, then rerun it.")
        if run.changed_files:
            files = ", ".join(item["path"] for item in run.changed_files[:3])
            procedure.append(f"Limit the patch to the observed area: {files}.")

        skill = Skill(
            id=new_id("skill"),
            title=f"Resolve {run.task_cluster} failures",
            scope=scope,
            trigger=run.task_title,
            procedure=procedure,
            evidence_run_ids=[run.id],
            verifier=run.verifier,
            confidence=0.72 if len(tool_events) < 2 else 0.84,
            valid_until="dependency-lock-hash changes",
        )
        candidate = Candidate(
            id=new_id("cand"),
            base_version=run.agent_version,
            operations=[{"op": "ADD", "skill": skill.to_dict()}],
            rationale=f"Verified successful run {run.id} showed a reusable {run.task_cluster} procedure.",
            evidence_run_ids=[run.id],
        )
        return skill, candidate
