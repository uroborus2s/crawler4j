# 部署与运行说明

**项目名称：** 蛛行演略（crawler4j）
**文档状态：** 已批准
**负责人：** 当前仓库维护者
**主要读者：** 维护者 | 发布负责人 | Dev
**上游输入：** `docs/04-project-development/04-design/technical-selection.md` | 本地验证结果
**下游输出：** `docs/04-project-development/08-operations-maintenance/core-maintainer-guide.md` | `docs/02-user-guide/user-guide.md` | 后续运维文档
**关联 ID：** `OPS-001`, `OPS-002`, `OPS-003`, `REQ-001`, `REQ-003`, `REQ-004`
**最后更新：** 2026-03-26

## 1. 环境准备

```bash
uv sync
```

要求：

- Python `>=3.12`
- 使用 `uv` 管理依赖与命令

## 2. 当前推荐运行方式

### 桌面应用

```bash
uv run start
uv run python -m src.ui.app
```

说明：

- `uv run start` 现在是根项目的声明启动方式
- `uv run python -m src.ui.app` 仍可作为显式调试入口

### 测试

```bash
uv run pytest -q
```

### Root / SDK / Contracts build

```bash
uv build --out-dir /tmp/crawler4j-build-check
cd crawler4j_sdk && uv build --out-dir /tmp/crawler4j-sdk-build-check
cd crawler4j_contracts && uv build --out-dir /tmp/crawler4j-contracts-build-check
```

### SDK CLI

```bash
uv run python -m crawler4j_sdk.cli.commands --help
```

## 3. 当前已知运行注意事项

- `ctrip labor_workflow` 已恢复到真实执行链，但真实站点 E2E 仍需单独验证

## 4. 发布前建议最小检查

1. `uv run pytest -q`
2. Root / SDK / Contracts build
3. 根应用入口 smoke
4. 版本号与 release notes 对齐检查

## 5. 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-03-28 | 同步四大模块结构下的上下游文档路径 | Codex |
| 2026-03-26 | 初始部署与运行说明 | Codex |
