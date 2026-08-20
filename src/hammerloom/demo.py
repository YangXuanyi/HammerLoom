from __future__ import annotations

from .service import HammerLoom


def seed_demo(guard: HammerLoom) -> str:
    if guard.store.all("runs"):
        return "Demo data already exists."
    first = guard.start_run("issue-17", "Fix migration schema mismatch", "migration")
    first.model("gpt-4.1", "Analyze schema mismatch", "Inspect migration state first.", tokens=940, duration_ms=2200)
    first.tool("shell", "pytest tests/migration -q", "FAILED schema version mismatch", 1200)
    first.tool("shell", "rg \"schema_version\" migrations tests", "Found stale expected version", 240)
    first.diff("migrations/validator.py", "- expected = 3\n+ expected = current_schema.version")
    first.verification("pytest tests/migration -q", True, "3 passed", 800)
    first.finish(True, "Validated the live schema version instead of a hard-coded migration number.")
    candidate = guard.compile_latest(first.id)
    guard.evaluate(candidate.id, {"current_success": 0.92, "regression_drop": 0.01, "ood_success": 0.78, "token_delta": 0.06, "safety_violations": 0})

    second = guard.start_run("issue-19", "Prevent duplicate migration metadata", "migration")
    second.model("gpt-4.1", "Review metadata lifecycle", "Use existing migration validation procedure.", tokens=710, duration_ms=1600)
    second.tool("shell", "pytest tests/migration -q", "3 passed", 770)
    second.verification("pytest tests/migration -q", True, "4 passed", 770)
    second.finish(True, "Reused the active migration Skill and verified the regression suite.")
    return "Seeded two runs, one verified Skill, and one promoted policy version."
