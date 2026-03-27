# Gemini 项目说明

默认先读压缩入口，不要全文加载长篇说明。

项目根目录：`.`
项目名称：`crawler4j`

优先读取顺序：
- `.factory/memory/runtime-brief.md`
- `.factory/memory/role-charter.project.md`
- `.factory/memory/motivation-state.md`
- `.factory/memory/autonomy-rules.md`
- `.factory/memory/evolution-baseline.md`
- `.factory/project.json`
- 当前阶段核心文档

全局补充协议：
- `../../AiProject/shanforge/skills/software-factory-cli/references/ai-runtime-protocol.md`
- `../../AiProject/shanforge/skills/software-factory-cli/references/ai-role-charter.md`

Gemini 默认职责：
- 需求、分析、架构、影响分析、复核

规则：
- 默认不要全文读取人类长文档。
- `AGENTS.md` / `GEMINI.md` 只保留稳定协作入口，不写安装结果、测试状态或当天运行结论。
- 编写需求后先看 `requirements-verification.md`。
- 进入实现前先看 `technical-selection.md`。
- 需要视觉交付时优先看 `docs/03-solution/ux-ui-design.md` 和 `docs/03-solution/assets/`。
