# 运行手册

**项目名称：** 蛛行演略（crawler4j）
**文档状态：** 已批准
**负责人：** 当前仓库维护者
**主要读者：** 运维 | Core 维护者 | 发布负责人 | 管理员
**上游输入：** `deployment-guide.md` | `core-maintainer-guide.md` | `docs/02-user-guide/configuration.md` | `docs/02-user-guide/usage.md`
**下游输出：** 故障排查结论 | 交接说明 | `.factory/memory/`
**关联 ID：** `OPS-004`, `OPS-005`, `TASK-018`, `REQ-004`
**最后更新：** 2026-04-02

## 1. 文档边界

- `deployment-guide.md` 负责说明怎么部署和启动。
- 本文负责说明怎么巡检、怎么判断故障、怎么恢复和何时升级。
- `core-maintainer-guide.md` 负责说明谁接手仓库和哪些文档要同步。

## 2. 日常巡检清单

| 检查项 | 期望结果 | 失败时先看哪里 |
|---|---|---|
| 宿主应用可启动 | `uv run python -m src.ui.app` 或打包产物可打开 | `deployment-guide.md`、UI smoke 结果 |
| 应用数据目录存在 | `config.db`、`state.db`、`logs/`、`modules/` 已创建 | `installation.md` |
| 模块列表正常 | `📦 模块管理` 可打开，来源和状态可识别 | `usage.md`、`admin-guide.md` |
| 配置可保存 | `🔧 系统设置` 与模块设置能写入 `config.db` | `configuration.md` |
| 日志持续生成 | `<app-data>/logs/` 正常滚动 | 日志级别与保留设置 |

## 3. 常见故障与第一响应

| 故障信号 | 第一判断 | 第一动作 |
|---|---|---|
| 应用打不开 | 入口或依赖环境异常 | 重新执行 `uv sync --all-packages`，再跑 `uv run python scripts/smoke_test_ui.py` |
| 模块能看到但跑不起来 | 执行配置或模块来源错误 | 核对 `execution.module`、`execution.workflow`、模块来源 |
| `🐞 调试` 按钮不出现 | 不是 DevLink 或运行模板未绑定 | 先检查 DevLink 来源和运行模板 |
| 正式安装模块与本地源码冲突 | 同名 DevLink 未按预期切换 | 在 `📦 模块管理` 里确认来源是否已变为正式安装模块 |
| 发布口径不清楚 | 版本、tag 和文档不同步 | 回到 `version-governance.md` 和 `release-notes.md` |

## 4. 恢复动作

### 启动故障

1. 执行 `uv sync --all-packages`。
2. 执行 `uv run python -m src.ui.app`。
3. 若仍失败，执行 `uv run python scripts/smoke_test_ui.py`。
4. 检查应用数据目录下的 `logs/`，再决定是否升级给 Core 维护者。

### 模块运行故障

1. 打开 `📦 模块管理` 确认模块来源和状态。
2. 打开任务运行模板，核对 `execution.module` 与 `execution.workflow`。
3. 若是 DevLink 联调问题，回到开发者指南的调试章节。
4. 若是正式安装链路问题，按管理员指南重走 zip 安装与验收路径。

## 5. 升级条件

以下情况不要继续在运行层面兜圈子，应直接升级给 Core 维护者：

1. 根应用入口、打包入口或 CLI 行为与设计文档冲突。
2. 模块运行契约、`module.yaml` 解析或 SDK 组装器行为异常。
3. 需要修改代码、测试或正式设计文档才能继续排障。

## 6. 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-04-02 | 新增正式运行手册并收敛日常巡检与故障响应动作 | Codex |
