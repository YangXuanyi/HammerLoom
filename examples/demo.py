"""运行代码修复 Agent，记录 HammerLoom 证据并启动 Studio 可视化。"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List

import uvicorn

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from hammerloom import HammerLoom
from hammerloom.api import create_app
from code_repair_agent import AgentEvent, create_agent

DATABASE_PATH = PROJECT_ROOT / ".hammerloom" / "qwen-agent-demo.db"
TRAJECTORY_DIR = PROJECT_ROOT / ".hammerloom" / "agent-trajectories"
TARGET_PROJECT_DIR = Path(__file__).resolve().parent / "pricing_repair_target"
STUDIO_HOST = "127.0.0.1"
STUDIO_PORT = 8766


def event_payload(index: int, event: AgentEvent) -> Dict[str, Any]:
    """将 AgentEvent 转换为可持久化的轨迹记录。"""
    return {"step": index, **asdict(event)}


def record_to_hammerloom(run: Any, event: AgentEvent) -> None:
    """将 Agent 事件映射为 HammerLoom 的模型、工具、补丁或验证证据。"""
    if event.kind == "model":
        run.model(
            event.name,
            event.input,
            event.output,
            tokens=int(event.attributes.get("tokens", 0)),
            duration_ms=event.duration_ms,
        )
    elif event.kind == "tool":
        run.tool(event.name, event.input, event.output, duration_ms=event.duration_ms)
    elif event.kind == "diff":
        run.diff(event.name, event.output)
    elif event.kind == "verification":
        run.verification(
            event.name,
            passed=bool(event.attributes["passed"]),
            output=event.output,
            duration_ms=event.duration_ms,
        )
    else:
        run.event(event.kind, event.name, event.input, event.output, event.duration_ms, **event.attributes)


def save_trajectory(run_id: str, events: List[Dict[str, Any]], result: Dict[str, Any]) -> None:
    """将完整执行轨迹和最终结果写入独立 JSON 文件。"""
    TRAJECTORY_DIR.mkdir(parents=True, exist_ok=True)
    path = TRAJECTORY_DIR / f"{run_id}.json"
    path.write_text(
        json.dumps({"run_id": run_id, "events": events, "result": result}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def run_agent() -> None:
    """运行 Agent 并将其完整执行证据写入 HammerLoom 和轨迹文件。"""
    guard = HammerLoom(str(DATABASE_PATH), repo_scope="repo:pricing-repair-target")
    run = guard.start_run(
        task_id="issue-pricing-1",
        task_title="修复当前工作目录中的代码问题",
        task_cluster="code-repair",
    )
    trajectory: List[Dict[str, Any]] = []
    result_payload: Dict[str, Any] = {"success": False, "summary": "Agent 尚未执行。"}

    def on_event(event: AgentEvent) -> None:
        """收集每个 Agent 事件，供 HammerLoom 和本地轨迹文件使用。"""
        record_to_hammerloom(run, event)
        trajectory.append(event_payload(len(trajectory) + 1, event))

    try:
        agent = create_agent(target_dir=TARGET_PROJECT_DIR, on_event=on_event)
        result = agent.repair()
        run.finish(success=result.success, summary=result.summary)
        result_payload = {
            "success": result.success,
            "summary": result.summary,
            "diagnosis": result.diagnosis,
            "patch": result.patch,
        }
        if result.success:
            candidate = guard.compile_latest(run.id)
            decision = guard.evaluate(candidate.id)
            result_payload["candidate_id"] = candidate.id
            result_payload["promotion_verdict"] = decision.verdict
    except Exception as exc:
        result_payload = {"success": False, "summary": "Agent 执行异常。", "error": str(exc)}
        run.finish(success=False, summary=result_payload["summary"])
    finally:
        save_trajectory(run.id, trajectory, result_payload)
        guard.close()


def run_studio() -> None:
    """在本地启动 HammerLoom Studio，展示本次及历史运行数据。"""
    url = f"http://{STUDIO_HOST}:{STUDIO_PORT}"
    print(f"HammerLoom Studio 已启动，请在浏览器打开：{url}")
    app = create_app(str(DATABASE_PATH))
    uvicorn.run(app, host=STUDIO_HOST, port=STUDIO_PORT, log_level="critical", access_log=False)


def main() -> None:
    """先运行 Agent 采集证据，再启动网页可视化服务。"""
    # run_agent()
    run_studio()


if __name__ == "__main__":
    main()
