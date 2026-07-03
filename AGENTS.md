DO NOT send optional commentary

# AI 软件工厂规则

默认不要散读整仓文档。

项目根目录：`.`
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

- `../../AiProject/shanforge/skills/software-factory-cli/references/ai-runtime-protocol.md`
- `../../AiProject/shanforge/skills/software-factory-cli/references/ai-role-charter.md`

规则：

- 默认不全文加载人类长文档。
- `AGENTS.md` / `GEMINI.md` 只保留稳定协作入口，不写安装结果、测试状态或当天运行结论。
- 只在解释背景、方案原理或用户明确要求时读取 `docs/*.md` 中的相关长文。
- 代码类工作必须走 PR 闭环。
- 变更必须同步代码、文档、测试、`.factory/memory/`。
