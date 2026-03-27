# 接手与日常使用指南

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** 新维护者 | 开发 | QA  
**上游输入：** `docs/07-operations/deployment-guide.md` | `.factory/memory/project-index.md`  
**下游输出：** 后续交接文档与管理员手册  
**关联 ID：** `DOC-001`, `DOC-002`, `REQ-005`  
**最后更新：** 2026-03-26  

## 1. 先看什么

1. `AGENTS.md` 或 `GEMINI.md`
2. `.factory/project.json`
3. `.factory/memory/current-state.md`
4. `docs/01-discovery/current-state-analysis.md`
5. `docs/04-delivery/task-breakdown.md`

## 2. 常用命令

```bash
uv sync
uv run start
uv run pytest -q
uv run python -m src.ui.app
uv run python -m crawler4j_sdk.cli.commands --help
```

## 3. 你当前最该记住的事实

- 测试、UI smoke、root/sdk/contracts build 都能通过
- 根应用 `start` 脚本与打包 spec 已修复
- `ctrip` 模块完整工作流已恢复基础运行时兼容，但真实站点 E2E 仍待单独回放
- 根应用工作区版本、运行时镜像与最近正式 tag 的关系已经统一并写入发布文档
- 当前工厂阶段是 `IMPLEMENTATION`

## 4. 下一步怎么推进

- 模块开发者指南已经完成当前轮优化，可直接用于外部模块作者开发、调试与安装验收
- `TASK-005` 已完成；当前默认质量门与文档导航规则见 `docs/05-quality/quality-gates.md`
- 当前下一步更适合转向 `ctrip` 真实站点 E2E 回放或发布收口

## 5. 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-03-26 | 初始接手指南 | Codex |
