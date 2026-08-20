# HammerLoom
Given tasks and a base model, forge a self-evolving agent.
HammerLoom是一个面向agent自进化的智能框架。针对一个需要搭建本地模型驱动的agent业务场景，框架会通过自动运行任务，迭代agent提示词、创建tool、生成skill、微调基座模型、优化agent编排。在一段时间后，自动成长为完全胜任该场景的专家级agent。重要的是，整个过程全部自动化实现，何时迭代，何时微调都由框架自己决定。

> **背景图生图 Prompt**
>
> `A cinematic ultra-wide background for an open-source AI engineering project called HammerLoom. Depict a self-evolving software agent as an abstract, precise intelligence system rather than a humanoid robot: a dark graphite workspace with a central luminous weave of structured execution traces, modular tool nodes, and an evolving agent workflow graph. Three clearly differentiated but unlabeled layers flow from left to right: runtime context and reusable skills as compact amber data threads; controlled model-parameter learning as a restrained teal neural lattice; agent architecture and multi-agent orchestration as a clean green-blue topology of connected modules. Around the evolution loop, show subtle verification gates, evidence links, regression test paths, sandbox boundaries, version checkpoints, and rollback branches, conveying safe, auditable, evidence-driven self-improvement. The system should feel technical, disciplined, and trustworthy, with crisp thin lines, high information density, subtle depth, restrained glow, dark charcoal background with teal, amber, and green accents. Keep the center and upper-left visually calm for README title overlay. No text, no letters, no logos, no people, no humanoid robots, no neon cyberpunk city, no floating holographic UI panels, no purple gradient, no clutter. Premium technical illustration, 21:9 aspect ratio.`

## Agent 三类受控进化
### 1 运行时 Context 与 Skill 进化
-当前方案及问题： 现有agent自进化的做法是摘要成功轨迹收入经验库、按照相似度检索经验库调用成功经验。但是这种做法存在3个问题：1.相似任务不一定适用的经验被错误复用；2.偶然成功或过期经验污染经验库；3.无法确认经验是否真正提升成功率，是否造成旧任务退化或产生一些用户无法承受的额外成本。
- 我们的解决方案：将每次轨迹先编译为带有适用条件、来源证据、验证器和失效条件的经验候选；在新任务、历史回归任务、OOD任务和安全/成本约束下进行影子评测，只有确认收益且无明显退化的候选才晋升为长期经验，并支持后续废弃与回滚。

### 2 模型参数进化（SFT / RL）
当agent轨迹积累到一定数量时or非参数优化达到性能上线时，框架将自行对base模型进行SFT或RL训练
- 当前方案及问题：SFT和RL的根本问题不是“有没有足够多的轨迹”，而是无法把一次任务结果可靠地转化为正确的参数更新。SFT只会模仿被选中的完整轨迹：成功轨迹可能依赖偶然的工具状态、检索上下文或冗余试错，失败轨迹中本可复用的局部正确决策则被丢弃，因此模型容易学习表面动作模式而非可迁移的决策能力。RL虽然能利用成败反馈探索，但Agent任务通常是长视界、部分可观测且环境动态变化的，最终稀疏奖励无法判断规划、工具选择、参数填写和错误恢复中哪一步应被奖励或惩罚；奖励模型不完备时，策略还会优化可得分的代理目标而非真实任务目标。
- 我们的解决方案：不将“成功/失败轨迹”直接等同于训练样本或奖励，而是先由阶段一的验证器把轨迹分解为可复现的任务结果、步骤级证据、失败归因和适用条件；SFT只蒸馏跨任务稳定有效的决策片段及其上下文，RL则以任务结果为锚，结合步骤验证和反事实对比构造可归因的过程奖励，并将无法解释的奖励增益隔离。


### Agent 架构拓扑与编排进化
针对跨任务等问题，框架将通过实验锁定最优agent编排策略，生成一个适用于当前任务的agent结构
- 当前方案及问题：现有ADAS、AFlow、AgentSquare等方法将Agent拓扑、角色和工作流作为搜索空间，通过整条工作流的最终任务分数选择候选。根本问题在于，工作流的最终成败无法归因到具体的角色、节点、通信边或控制流：一次提升可能来自更强模型、更多采样或偶然工具状态，而非新增的规划器、审查器或协作链路；因此搜索容易在有限验证集上堆叠冗余调用，学到不能迁移的“评测专用拓扑”。同时，拓扑空间随角色、工具和通信方式组合爆炸，离线搜索成本高；即使离线最优结构，也未必能在不同任务难度、上下文状态和延迟/token预算下持续最优。多Agent场景还会出现无效通信、循环委派和局部目标与全局目标脱节，单看成功率无法暴露这些问题。
- 我们的解决方案：不直接从全量拓扑中搜索“最高分工作流”，而是先依据阶段一、二积累的失败簇和步骤级证据诊断瓶颈，再提出带有适用任务特征、预期作用、资源上限和可验证退出条件的最小编排变更候选，例如增加校验节点、调整工具路由、并行化独立子任务或删除冗余协作边。对候选进行全面评测，只有在任务簇与历史回归任务上均确认净收益的结构才晋升。



