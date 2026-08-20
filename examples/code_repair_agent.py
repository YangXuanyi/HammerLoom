"""通用代码修复Agent。

该示例中的 Agent 在指定工作目录内完成检查、诊断、修改和验证，并将每次
模型决策、工具调用、补丁和验证结果以 AgentEvent 暴露给 HammerLoom。
"""

from __future__ import annotations

import difflib
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from openai import OpenAI


@dataclass
class AgentEvent:
    kind: str
    name: str
    input: str = ""
    output: str = ""
    duration_ms: int = 0
    attributes: Dict[str, object] = field(default_factory=dict)


@dataclass
class RepairResult:
    success: bool
    summary: str
    diagnosis: str
    patch: str = ""
    events: List[AgentEvent] = field(default_factory=list)


class QwenLLM:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> None:
        """初始化 Qwen 兼容接口客户端及生成参数。"""
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def chat(self, messages: List[Dict[str, str]]) -> Tuple[str, int, int]:
        """向 Qwen 发送完整对话，并返回文本、耗时和实际 token 用量。"""
        started = time.perf_counter()
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        usage = response.usage.total_tokens if response.usage else 0
        return response.choices[0].message.content or "", int((time.perf_counter() - started) * 1000), usage


class CodeRepairAgent:
    """代码修复agent"""

    SYSTEM_PROMPT = """你是一名代码修复Agent。目标是修复指定工作目录中的项目，并用真实测试验证。
每一轮只能输出一个 JSON 对象，格式如下：
{"thought":"简短中文推理","action":"工具名","input":{}}

可用工具：
- list_files：input 可为 {"pattern":"**/*.py"}，列出工作目录内匹配的文件。
- search_text：input 为 {"query":"文本", "pattern":"**/*.py"}，在文本文件中搜索。
- read_file：input 为 {"path":"相对路径"}，读取一个文件。
- run_tests：input 为 {"command":["python","-m","unittest","discover","-s","tests","-v"]}。仅用于运行测试、类型检查或构建验证命令；不能使用 shell、重定向或命令连接符。
- apply_patch：input 为 {"path":"相对路径", "old_text":"待替换的完整原文", "new_text":"替换后的完整文本"}。原文必须在文件中恰好出现一次。
- finish：input 为 {"summary":"中文修复摘要", "diagnosis":"中文根因分析"}。

规则：先运行测试或验证命令获取真实失败信息；必要时再检查文件；修改必须使用 apply_patch；修改后必须运行测试；只有最近一次测试通过时才能 finish。所有路径必须相对于工作目录。不要使用 Markdown 或额外文本。"""
    MAX_STEPS = 12
    MAX_FILE_SIZE = 100_000
    ALLOWED_COMMANDS = {"python", "pytest", "npm", "node", "go", "cargo"}

    def __init__(
        self,
        target_dir: Path,
        llm: QwenLLM,
        on_event: Optional[Callable[[AgentEvent], None]] = None,
    ) -> None:
        """绑定受限工作目录、模型客户端和可选的事件回调。"""
        self.target_dir = target_dir.resolve()
        self.llm = llm
        self.on_event = on_event
        self.events: List[AgentEvent] = []

    def emit(self, event: AgentEvent) -> None:
        """保存 Agent 运行事件，并同步通知外部观测回调。"""
        self.events.append(event)
        if self.on_event:
            self.on_event(event)

    def resolve_path(self, relative_path: str) -> Path:
        """解析工作目录内的相对路径，并拒绝目录逃逸访问。"""
        path = (self.target_dir / relative_path).resolve()
        if path != self.target_dir and self.target_dir not in path.parents:
            raise RuntimeError("文件路径超出了 Agent 工作目录。")
        return path

    def list_files(self, pattern: str = "**/*") -> str:
        """列出工作目录中匹配模式的普通文件，并忽略缓存和 Git 元数据。"""
        files = [
            str(path.relative_to(self.target_dir))
            for path in self.target_dir.glob(pattern)
            if path.is_file() and "__pycache__" not in path.parts and ".git" not in path.parts
        ]
        output = "\n".join(sorted(files)[:200])
        self.emit(AgentEvent("tool", "list_files", pattern, output))
        return output

    def read_file(self, relative_path: str) -> str:
        """读取工作目录内的 UTF-8 文本文件，并记录读取事件。"""
        path = self.resolve_path(relative_path)
        if not path.is_file():
            raise RuntimeError(f"文件不存在：{relative_path}")
        if path.stat().st_size > self.MAX_FILE_SIZE:
            raise RuntimeError(f"文件过大，拒绝读取：{relative_path}")
        content = path.read_text(encoding="utf-8")
        self.emit(AgentEvent("tool", "read_file", relative_path, content))
        return content

    def search_text(self, query: str, pattern: str = "**/*") -> str:
        """在匹配的文本文件中搜索内容，并返回带行号的命中结果。"""
        if not query:
            raise RuntimeError("搜索文本不能为空。")
        matches: List[str] = []
        for path in self.target_dir.glob(pattern):
            if not path.is_file() or "__pycache__" in path.parts or path.stat().st_size > self.MAX_FILE_SIZE:
                continue
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except UnicodeDecodeError:
                continue
            for line_number, line in enumerate(lines, start=1):
                if query in line:
                    matches.append(f"{path.relative_to(self.target_dir)}:{line_number}: {line}")
                    if len(matches) >= 100:
                        break
            if len(matches) >= 100:
                break
        output = "\n".join(matches) or "未找到匹配文本。"
        self.emit(AgentEvent("tool", "search_text", json.dumps({"query": query, "pattern": pattern}, ensure_ascii=False), output))
        return output

    def run_tests(self, command: Sequence[str]) -> Tuple[bool, str]:
        """在工作目录执行受白名单限制的验证命令，并返回通过状态和输出。"""
        if not command or not all(isinstance(item, str) and item for item in command):
            raise RuntimeError("测试命令必须是非空字符串数组。")
        executable = command[0]
        if executable not in self.ALLOWED_COMMANDS:
            raise RuntimeError(f"不允许执行的命令：{executable}")
        if any(item in {"|", ">", ">>", "&&", ";"} for item in command):
            raise RuntimeError("测试命令不能包含 shell 操作符。")
        normalized_command = [sys.executable, *command[1:]] if executable == "python" else list(command)
        started = time.perf_counter()
        completed = subprocess.run(normalized_command, cwd=self.target_dir, capture_output=True, text=True)
        duration_ms = int((time.perf_counter() - started) * 1000)
        output = (completed.stdout + completed.stderr).strip()
        self.emit(AgentEvent("tool", "run_tests", " ".join(command), output, duration_ms))
        return completed.returncode == 0, output

    def apply_patch(self, relative_path: str, old_text: str, new_text: str) -> str:
        """在旧文本唯一匹配时写入精确替换，并返回统一格式补丁。"""
        if not old_text:
            raise RuntimeError("补丁的 old_text 不能为空。")
        path = self.resolve_path(relative_path)
        before = self.read_file(relative_path)
        occurrences = before.count(old_text)
        if occurrences != 1:
            raise RuntimeError(f"old_text 必须在文件中恰好出现一次，实际出现 {occurrences} 次。")
        after = before.replace(old_text, new_text, 1)
        path.write_text(after, encoding="utf-8")
        patch = "".join(
            difflib.unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile=f"a/{relative_path}",
                tofile=f"b/{relative_path}",
            )
        )
        self.emit(AgentEvent("diff", relative_path, "", patch))
        return patch

    @staticmethod
    def parse_action(response: str) -> Dict[str, object]:
        """校验并解析模型返回的 ReAct JSON 决策。"""
        try:
            decision = json.loads(response)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"模型未返回有效的 ReAct JSON：{response}") from exc
        if not isinstance(decision, dict) or set(decision) != {"thought", "action", "input"}:
            raise RuntimeError("模型响应必须且只能包含 thought、action 和 input。")
        if not isinstance(decision["thought"], str) or not isinstance(decision["action"], str):
            raise RuntimeError("thought 和 action 必须为字符串。")
        if not isinstance(decision["input"], dict):
            raise RuntimeError("input 必须为 JSON 对象。")
        return decision

    def execute_action(self, action: str, tool_input: Dict[str, object]) -> str:
        """将模型指定的动作路由到受控工具，并返回工具观察结果。"""
        if action == "list_files":
            return self.list_files(str(tool_input.get("pattern", "**/*")))
        if action == "search_text":
            return self.search_text(str(tool_input.get("query", "")), str(tool_input.get("pattern", "**/*")))
        if action == "read_file":
            return self.read_file(str(tool_input.get("path", "")))
        if action == "run_tests":
            command = tool_input.get("command")
            if not isinstance(command, list):
                raise RuntimeError("run_tests 的 command 必须是字符串数组。")
            passed, output = self.run_tests(command)
            return json.dumps({"passed": passed, "output": output}, ensure_ascii=False)
        if action == "apply_patch":
            return self.apply_patch(
                str(tool_input.get("path", "")),
                str(tool_input.get("old_text", "")),
                str(tool_input.get("new_text", "")),
            )
        raise RuntimeError(f"不允许的工具调用：{action}")

    def repair(self, task: str = "修复当前工作目录中的测试失败，并完成真实验证。") -> RepairResult:
        """运行有限步数的 ReAct 修复循环，并返回已验证的修复结果。"""
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": f"工作目录：{self.target_dir.name}\n任务：{task}"},
        ]
        patch = ""
        diagnosis = ""
        last_test_passed = False
        last_test_command = ""
        last_test_output = ""

        for _ in range(self.MAX_STEPS):
            response, duration_ms, tokens = self.llm.chat(messages)
            self.emit(
                AgentEvent(
                    "model",
                    "qwen-plus",
                    messages[-1]["content"],
                    response,
                    duration_ms,
                    {"tokens": tokens},
                )
            )
            decision = self.parse_action(response)
            messages.append({"role": "assistant", "content": response})
            action = str(decision["action"])
            tool_input = decision["input"]

            if action == "finish":
                if not last_test_passed:
                    raise RuntimeError("结束任务前必须运行并通过测试。")
                try:
                    summary = str(tool_input["summary"])
                    diagnosis = str(tool_input["diagnosis"])
                except KeyError as exc:
                    raise RuntimeError("finish 的 input 必须包含 summary 和 diagnosis。") from exc
                self.emit(
                    AgentEvent(
                        "verification",
                        last_test_command,
                        output=last_test_output,
                        attributes={"passed": True},
                    )
                )
                return RepairResult(True, summary, diagnosis, patch, self.events)

            observation = self.execute_action(action, tool_input)
            if action == "run_tests":
                last_test_passed = bool(json.loads(observation)["passed"])
                last_test_command = " ".join(str(item) for item in tool_input["command"])
                last_test_output = json.loads(observation)["output"]
                if last_test_passed and not patch:
                    diagnosis = "初始测试已通过，未发现需要修复的问题。"
                    summary = "测试已通过，无需修改工作目录。"
                    self.emit(
                        AgentEvent(
                            "verification",
                            last_test_command,
                            output=last_test_output,
                            attributes={"passed": True},
                        )
                    )
                    return RepairResult(True, summary, diagnosis, events=self.events)
            elif action == "apply_patch":
                patch = observation
                last_test_passed = False
            messages.append(
                {"role": "user", "content": f"Observation ({action})：\n{observation}\n请继续选择下一步。"}
            )

        return RepairResult(False, "ReAct 循环超过最大步数，停止自动修复。", diagnosis, patch, self.events)


def load_llm_config(config_path: Optional[Path] = None) -> Dict[str, object]:
    """读取并校验 LLM 配置文件中的连接与生成参数。"""
    path = config_path or Path(__file__).parent / "agent_config.json"
    try:
        config = json.loads(path.read_text(encoding="utf-8"))["llm"]
    except (FileNotFoundError, KeyError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"无法读取 LLM 配置文件: {path}") from exc
    if not config.get("api_key") or config["api_key"] == "请填入你的 DashScope API Key":
        raise RuntimeError(f"请先在 {path} 的 llm.api_key 中填写 API Key。")
    return config


def create_agent(
    target_dir: Optional[Path] = None,
    on_event: Optional[Callable[[AgentEvent], None]] = None,
    config_path: Optional[Path] = None,
) -> CodeRepairAgent:
    """根据配置创建绑定目标目录的通用代码修复 Agent。"""
    config = load_llm_config(config_path)
    target = target_dir or Path(__file__).parent / "pricing_repair_target"
    llm = QwenLLM(
        api_key=str(config["api_key"]),
        base_url=str(config["base_url"]),
        model=str(config["model"]),
        temperature=float(config["temperature"]),
        max_tokens=int(config["max_tokens"]),
    )
    return CodeRepairAgent(target, llm, on_event)


if __name__ == "__main__":
    agent = create_agent()
    result = agent.repair()
    print(result.diagnosis)
    print(result.summary)
