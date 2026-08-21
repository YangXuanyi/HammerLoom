# ToolSandbox Skill Evaluation

这个实验使用 Apple 的 ToolSandbox 公共基准，验证 HammerLoom 第一阶段“Context 与 Skill 进化”方法。它不是 HammerLoom 的通用运行时依赖，而是一组可复现的外部实验任务。

## 实验目标

每个任务在相同初始状态下成对运行：

1. 基线策略不加载候选 Skill；
2. 对照策略在满足前置条件时加载候选 Skill；
3. 比较任务完成度、milestones、工具调用轨迹、token、耗时、成本和安全事件；
4. 仅当候选 Skill 在来源、相似、历史、不同类型和安全任务中表现出稳定净收益时，才允许晋升。

ToolSandbox 提供带状态的工具环境、用户模拟器及基于 milestones 和 minefields 的自动评测。它的世界状态包含系统设置、联系人、消息和提醒事项。

## 目录

```text
ToolSandbox/
  run.py                 实验入口
  dataset/
    manifest.json        精选任务、分组和 development/holdout 划分
    tool_sandbox/        上游 ToolSandbox 运行代码与场景定义
    README.md            上游项目说明
    LICENSE              上游许可证
```

`dataset/manifest.json` 选择 16 个官方场景。开发集有 8 个任务，可用于候选 Skill 的生成和调试；保留集有 8 个任务，只能在最终评测阶段使用。

## 安装

建议使用 Python 3.9 到 3.12 的隔离虚拟环境：

```powershell
cd f:\Code_Project\HammerLoom\examples\ToolSandbox\dataset
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

两个实验共用 `examples/.env`。填写以下变量：

```dotenv
TOOL_SANDBOX_API_KEY=ToolSandbox 使用的 OpenAI 兼容接口 Key
TOOL_SANDBOX_BASE_URL=ToolSandbox 使用的 OpenAI 兼容接口 URL
TOOL_SANDBOX_AGENT_MODEL=ToolSandbox Agent 角色类型
TOOL_SANDBOX_USER_MODEL=ToolSandbox 用户模拟器角色类型
```

`run.py` 会自动加载该文件，并在运行 ToolSandbox 前映射为上游所需的 `OPENAI_API_KEY` 与 `OPENAI_BASE_URL`。本实验精选的场景仅操作 Sandbox 本地状态，不需要 RapidAPI 或其他网络搜索 Key。不同 Agent 类型的额外要求请参阅 `dataset/README.md`。

## 运行

先查看开发集执行计划，不调用模型：

```powershell
cd f:\Code_Project\HammerLoom\examples\ToolSandbox
python run.py --split development --dry-run
```

运行开发集：

```powershell
python run.py --split development --parallel 1
```

默认模型由 `examples/.env` 中的 `TOOL_SANDBOX_AGENT_MODEL` 和 `TOOL_SANDBOX_USER_MODEL` 指定；传入 `--agent` 或 `--user` 可以仅对本次运行覆盖它们。

运行单个保留任务：

```powershell
python run.py --split holdout --scenario turn_on_cellular_low_battery_mode --dry-run
```

默认结果目录：

```text
dataset/data/development/
dataset/data/holdout/
```

每次运行会创建按 Agent、用户模拟器和时间戳区分的结果目录。`result_summary.json` 保存每个场景的相似度和里程碑统计，`trajectories/<场景名>/conversation.json` 保存完整交互轨迹。

## 实验约束

- 每个基线和候选运行使用相同场景、模型、初始状态、采样参数和资源上限。
- 每组至少重复运行多个固定种子，避免将一次随机成功视为 Skill 收益。
- `holdout` 不参与 Skill 生成、提示词调整或阈值选择。
- 上游 ToolSandbox 工具在宿主 Python 进程中运行；实验应在隔离虚拟环境或容器中执行。
- 数据集和运行代码遵循 `dataset/LICENSE` 及 `dataset/ACKNOWLEDGEMENTS` 中的上游许可与致谢要求。
