"""运行 ToolSandbox Skill 评测实验。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

EXPERIMENT_DIR = Path(__file__).resolve().parent
DATASET_DIR = EXPERIMENT_DIR / "dataset"
ENV_PATH = EXPERIMENT_DIR.parent / ".env"

# 直接运行时的配置；模型留空则读取 examples/.env 中对应的变量。
SPLIT = "development"
SCENARIO_NAMES: list[str] | None = None
AGENT_MODEL = ""
USER_MODEL = ""
PARALLEL = 1
OUTPUT_DIR: Path | None = None
DRY_RUN = False


def load_env() -> None:
    """加载 examples/.env 中尚未设置的环境变量。"""
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def load_manifest() -> dict[str, Any]:
    with (DATASET_DIR / "manifest.json").open(encoding="utf-8") as file:
        return json.load(file)


def resolve_scenarios(
    manifest: dict[str, Any], split: str, scenario_names: list[str] | None
) -> list[str]:
    known_scenarios = {scenario["name"] for scenario in manifest["scenarios"]}
    selected = scenario_names or manifest["evaluation_split"][split]
    unknown = sorted(set(selected) - known_scenarios)
    if unknown:
        raise ValueError(f"场景不在 manifest.json 中: {', '.join(unknown)}")
    return selected


def main() -> None:
    load_env()
    agent = AGENT_MODEL or os.environ.get("TOOL_SANDBOX_AGENT_MODEL", "")
    user = USER_MODEL or os.environ.get("TOOL_SANDBOX_USER_MODEL", "")
    if not agent or not user:
        raise RuntimeError(
            "请先在 examples/.env 中填写 TOOL_SANDBOX_AGENT_MODEL 和 TOOL_SANDBOX_USER_MODEL。"
        )
    manifest = load_manifest()
    scenarios = resolve_scenarios(manifest, SPLIT, SCENARIO_NAMES)
    output_dir = (OUTPUT_DIR or DATASET_DIR / "data" / SPLIT).resolve()
    command = [
        sys.executable,
        "-m",
        "tool_sandbox.cli",
        "--agent",
        agent,
        "--user",
        user,
        "--scenarios",
        *scenarios,
        "--parallel",
        str(PARALLEL),
        "--output_dir",
        str(output_dir),
    ]
    print(
        json.dumps(
            {
                "experiment": "ToolSandbox Skill Evaluation",
                "split": SPLIT,
                "scenarios": scenarios,
                "output_dir": str(output_dir),
                "command": command,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if DRY_RUN:
        return

    environment = os.environ.copy()
    environment["OPENAI_API_KEY"] = environment.get("TOOL_SANDBOX_API_KEY", "")
    environment["OPENAI_BASE_URL"] = environment.get("TOOL_SANDBOX_BASE_URL", "")
    if not environment["OPENAI_API_KEY"] or environment["OPENAI_API_KEY"].startswith("请填入"):
        raise RuntimeError("请先在 examples/.env 中填写 TOOL_SANDBOX_API_KEY。")
    python_path = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        str(DATASET_DIR)
        if not python_path
        else str(DATASET_DIR) + os.pathsep + python_path
    )
    subprocess.run(command, cwd=DATASET_DIR, env=environment, check=True)


if __name__ == "__main__":
    main()
