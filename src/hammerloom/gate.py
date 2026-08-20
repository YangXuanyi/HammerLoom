from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


DEFAULT_POLICY = {
    "min_current_success": 0.75,
    "max_regression_drop": 0.05,
    "min_ood_success": 0.65,
    "max_tokens_delta": 0.20,
    "max_safety_violations": 0,
}


class PromotionGate:
    """Deterministic hard gate. Real runners can supply their measured dimensions."""

    def evaluate(self, results: Dict[str, Any], policy: Optional[Dict[str, Any]] = None) -> Tuple[str, Dict[str, Dict[str, Any]], List[str]]:
        policy = {**DEFAULT_POLICY, **(policy or {})}
        current = results.get("current_success", 0.0)
        regression_drop = results.get("regression_drop", 1.0)
        ood = results.get("ood_success", 0.0)
        token_delta = results.get("token_delta", 1.0)
        safety = results.get("safety_violations", 99)
        metrics = {
            "adaptation": {"value": current, "threshold": policy["min_current_success"], "passed": current >= policy["min_current_success"]},
            "retention": {"value": regression_drop, "threshold": policy["max_regression_drop"], "passed": regression_drop <= policy["max_regression_drop"]},
            "generalization": {"value": ood, "threshold": policy["min_ood_success"], "passed": ood >= policy["min_ood_success"]},
            "efficiency": {"value": token_delta, "threshold": policy["max_tokens_delta"], "passed": token_delta <= policy["max_tokens_delta"]},
            "safety": {"value": safety, "threshold": policy["max_safety_violations"], "passed": safety <= policy["max_safety_violations"]},
        }
        failed = [name for name, metric in metrics.items() if not metric["passed"]]
        if "safety" in failed:
            return "rejected", metrics, ["Safety policy has a hard failure."]
        if failed:
            return "manual_review", metrics, [f"Gate needs review: {', '.join(failed)}."]
        return "promoted", metrics, ["All adaptation, retention, generalization, efficiency, and safety gates passed."]
