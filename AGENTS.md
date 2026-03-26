# AI 软件工厂规则

默认不要散读整仓文档。

项目根目录：`/Users/uroborus/PythonProject/crawler4j`
项目名称：`crawler4j`

优先读取顺序：
- `.factory/memory/runtime-brief.md`
- `.factory/memory/role-charter.project.md`
- `.factory/memory/motivation-state.md`
- `.factory/memory/autonomy-rules.md`
- `.factory/memory/evolution-baseline.md`
- `.factory/project.json`
- `.factory/memory/current-state.md`
- 当前阶段核心文档

补充协议：
- `/Users/uroborus/.agent/skills/software-factory-cli/references/ai-runtime-protocol.md`
- `/Users/uroborus/.agent/skills/software-factory-cli/references/ai-role-charter.md`

规则：
- 默认不全文加载人类长文档。
- 只在解释背景、方案原理或用户明确要求时读取 `docs/*.md` 中的相关长文。
- 代码类工作必须走 PR 闭环。
- 变更必须同步代码、文档、测试、`.factory/memory/`。
