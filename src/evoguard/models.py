from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


@dataclass
class TraceEvent:
    kind: str
    name: str
    timestamp: str = field(default_factory=now)
    duration_ms: int = 0
    input: str = ""
    output: str = ""
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Run:
    id: str
    task_id: str
    task_title: str
    agent_version: str
    status: str = "running"
    success: Optional[bool] = None
    summary: str = ""
    task_cluster: str = "general"
    events: List[TraceEvent] = field(default_factory=list)
    changed_files: List[Dict[str, str]] = field(default_factory=list)
    verifier: str = ""
    tokens: int = 0
    duration_ms: int = 0
    created_at: str = field(default_factory=now)
    finished_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Skill:
    id: str
    title: str
    scope: str
    trigger: str
    procedure: List[str]
    evidence_run_ids: List[str]
    verifier: str
    confidence: float
    valid_until: str
    status: str = "candidate"
    risk: str = "low"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PolicyVersion:
    id: str
    parent_id: Optional[str]
    skill_ids: List[str]
    routing_rules: List[str]
    source_candidate_id: Optional[str] = None
    created_at: str = field(default_factory=now)
    state: str = "active"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Candidate:
    id: str
    base_version: str
    operations: List[Dict[str, Any]]
    rationale: str
    evidence_run_ids: List[str]
    status: str = "pending"
    created_at: str = field(default_factory=now)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PromotionDecision:
    id: str
    candidate_id: str
    verdict: str
    metrics: Dict[str, Dict[str, Any]]
    reasons: List[str]
    created_at: str = field(default_factory=now)
    promoted_version: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
