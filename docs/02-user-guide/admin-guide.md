# 管理员指南

**项目名称：** 蛛行演略（crawler4j）
**文档状态：** 已批准
**负责人：** 当前仓库维护者
**主要读者：** 管理员 | 实施者 | 现场支持
**上游输入：** `installation.md` | `configuration.md` | `usage.md` | `docs/04-project-development/08-operations-maintenance/deployment-guide.md`
**下游输出：** 现场交接说明 | `docs/04-project-development/07-release-delivery/acceptance-checklist.md` | `docs/04-project-development/08-operations-maintenance/operations-runbook.md`
**关联 ID：** `DOC-107`, `OPS-006`, `TASK-018`, `REQ-005`
**最后更新：** 2026-04-15

## 1. 你的职责边界

管理员 / 实施者负责环境初始化、宿主安装、模块安装、基础配置和交付验收。
如果问题已经进入代码、SDK 契约或架构边界层面，应升级给 Core 维护者，而不是继续在现场兜底。

## 2. 第一天接手检查清单

1. 按 [安装说明](installation.md) 完成源码运行或打包产物运行。
2. 首次启动宿主应用，确认应用数据目录已创建。
3. 确认 `config.db`、`state.db`、`logs/` 和 `modules/` 已出现。
4. 按 [配置说明](configuration.md) 检查网络、浏览器、日志保留等系统设置。
5. 按 [使用说明](usage.md) 走通一次模块安装或模块联调链路。

## 3. 模块管理职责

### 正式安装模块

1. 打开 `📦 模块管理`。
2. 通过 `📥 安装模块` 安装 zip。
3. 确认模块来源显示为正式安装模块。
4. 打开模块详情补齐配置。
5. 到 `📋 任务监控` 中创建任务，配置运行模板里的 `execution.module` 和 `execution.workflow`，并按业务选择 `批次任务`（执行一次 / Cron）或 `持续保活`。

### DevLink 模块

- DevLink 只用于联调，不用于正式交付。
- 当前调试链只对 DevLink 模块开放。
- 如果同名模块已经正式安装，正式安装过程会移除同名 DevLink。

## 4. 配置管理职责

| 配置层 | 你需要关心什么 |
|---|---|
| 系统设置 | 网络、浏览器、日志级别和日志保留天数 |
| 模块设置 | 模块配置表单是否可打开和保存 |
| 执行配置 | `execution.module` 必须等于 `module.yaml.name`，`execution.workflow` 必须等于目标工作流名，并且任务模式要与业务语义一致：单次人工发起选 `批次任务 + 执行一次`，定时批量执行选 `批次任务 + Cron`，常驻补齐并发选 `持续保活` |

注意：

- 语言和代理模式等部分设置需要重启后完全生效。
- 设置写入应用数据目录，不会回写到仓库源码。

## 5. 交付和验收时要看什么

1. 发布前执行 [验收检查清单](../04-project-development/07-release-delivery/acceptance-checklist.md)。
2. 对外或跨团队交付时补齐 [交付包清单](../04-project-development/07-release-delivery/delivery-package.md)。
3. 现场运行和故障处理按 [运行手册](../04-project-development/08-operations-maintenance/operations-runbook.md) 执行。

## 6. 何时升级给 Core 维护者

1. 根应用无法启动，且按安装/运行说明排查后仍失败。
2. 模块来源、模块配置或执行配置正确，但运行行为仍和文档冲突。
3. 需要修改 SDK、Core 代码、正式接口契约或测试才能解决问题。

## 7. 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-04-02 | 新增管理员指南并拆分管理员与普通使用者阅读路径 | Codex |
| 2026-04-15 | 补充 ATM 任务模式说明，明确 `批次任务` 支持“执行一次 / Cron”，`持续保活` 保持手动启动 | Codex |
