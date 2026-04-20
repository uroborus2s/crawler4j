# 部署与运行说明

**项目名称：** 蛛行演略（crawler4j）
**文档状态：** 已批准
**负责人：** 当前仓库维护者
**主要读者：** 维护者 | 发布负责人 | Dev
**上游输入：** `docs/04-project-development/04-design/technical-selection.md` | 本地验证结果
**下游输出：** `docs/04-project-development/08-operations-maintenance/operations-runbook.md` | `docs/04-project-development/08-operations-maintenance/core-maintainer-guide.md` | `docs/02-user-guide/user-guide.md` | `docs/02-user-guide/admin-guide.md`
**关联 ID：** `OPS-001`, `OPS-002`, `OPS-003`, `REQ-001`, `REQ-003`, `REQ-004`
**最后更新：** 2026-04-20

## 1. 环境准备

```bash
uv sync --all-packages
```

要求：

- Python `>=3.12`
- 使用 `uv` 管理依赖与命令

## 2. 当前推荐运行方式

### 桌面应用

```bash
uv run python -m src.ui.app
```

说明：

- workspace 根通过 `uv run python -m src.ui.app` 直接启动 `packages/crawler4j` 中的真实入口
- 若需要打包，PyInstaller 规格位于 `packages/crawler4j/crawler4j.spec`
- 正式桌面打包入口统一为 `uv run package-desktop`
- 当前 macOS 最终可分发产物固定为 `packages/crawler4j/dist/desktop/macos/Crawler4j.app`，不需要再额外携带旁边的 `Crawler4j/` collect 目录
- PyInstaller 现已显式收集 `sinanz` 的共享 `resources/` 目录，打包版验证码能力不应再因缺失 `slider_gap_locator.onnx` 等内嵌模型而退化

### 测试

```bash
uv run pytest -q
```

### Root / SDK / Contracts build

```bash
uv run build
```

说明：

- 脚本会在 workspace 根目录顺序构建 `crawler4j-sdk`、`crawler4j`、`crawler4j-contracts`
- 每个包在构建前都会通过 `uv build --clear` 清空自己的 `dist/`
- 产物分别落到 `packages/crawler4j-sdk/dist/`、`packages/crawler4j/dist/`、`packages/crawler4j-contracts/dist/`
- 如果只想构建一个包，可直接写 `uv run build crawler4j`
- 长命令 `uv run python scripts/build_workspace_packages.py ...` 仍可用，但正式口径优先使用短命令

### Publish SDK / Contracts to PyPI

```bash
UV_PUBLISH_TOKEN=<your-token> uv run publish crawler4j-sdk
UV_PUBLISH_TOKEN=<your-token> uv run publish crawler4j-contracts
```

说明：

- 若使用 PyPI token，优先设置 `UV_PUBLISH_TOKEN`
- 需要预演时可先执行 `UV_PUBLISH_TOKEN=<your-token> uv run publish crawler4j-sdk --dry-run`
- 若仓库后续配置了带 `publish-url` 的 `tool.uv.index`，也可以改用 `uv publish --index <name> ...`
- 脚本会自动把 `crawler4j-sdk` / `crawler4j-contracts` 映射到各自包目录下的 `dist/*`，不需要手写文件路径

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

## 5. docs-stratego 联动发布

- docs-stratego 源仓联动的正式口径以 `main` 为准：`.github/workflows/notify-docs-stratego.yml` 应监听 `main` 分支上的 `docs/**` 变更。
- workflow 只负责向 `uroborus2s/docs-stratego` 发送 `source-pointer-sync-requested` 事件，不在本仓直接构建或部署线上文档。
- 源仓必须在 GitHub Actions Secret 中配置 `DOCS_STRATEGO_DISPATCH_TOKEN`；该 token 只用于触发 `docs-stratego` 根仓的 `repository_dispatch`。
- workflow 会先去掉 `DOCS_STRATEGO_DISPATCH_TOKEN` 中意外带入的 `CR/LF` 再构造 `Authorization` header，避免凭据换行把 dispatch 请求拆断。
- `docs-stratego` 根仓的 source pointer 也应指向 `crawler4j` 的 `main`；如果后续切换到其他发布分支，需要同时更新源仓 workflow 分支过滤与根仓 `config/source-repos.json`。
- 根仓收到事件后会更新 `bot/sync-source-pointers` 共享 PR；线上文档仍以根仓审核合并后的 `main/master` 部署结果为准。

## 6. 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-04-20 | 补记桌面打包对 `sinanz` 共享 `resources/` 目录的显式收集约束，避免验证码模型资源在 PyInstaller 产物中丢失 | Codex |
| 2026-04-20 | 将 docs-stratego 联动发布说明从 `feature/task-plugin-system` 收敛到 `main` 分支口径，并补记 dispatch token 换行清理约束 | Codex |
| 2026-04-17 | 新增 `docs-stratego` 源仓通知 workflow，并补充共享 PR 联动发布说明 | Codex |
| 2026-04-02 | 下游输出补齐到运行手册和管理员指南 | Codex |
| 2026-03-28 | 同步四大模块结构下的上下游文档路径 | Codex |
| 2026-03-26 | 初始部署与运行说明 | Codex |
