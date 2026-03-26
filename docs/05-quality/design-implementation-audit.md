# 设计与实现一致性审查

**项目名称：** crawler4j  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** Tech Lead | Dev | QA | 发布负责人  
**上游输入：** `docs/03-solution/reference-design/` | `docs/02-requirements/reference-srs/` | 当前代码 | 当前命令验证结果  
**下游输出：** `.factory/workitems/` | `.factory/memory/current-state.md`  
**关联 ID：** `TASK-008`, `TASK-003`, `TASK-009`, `CR-003`  
**最后更新：** 2026-03-26  

## 1. 审查范围与方法

- 审查范围：MMS、ATM/Task Engine、Debug Session、模块外部安装链路、质量门。
- 对照输入：`docs/02-requirements/reference-srs/05-framework-core/05-1-module-management.md`、`docs/03-solution/reference-design/module-03-module-management.md`、`docs/03-solution/reference-design/design-strategy-config-v2.md`、`docs/03-solution/reference-design/model-debug-session.md`、`docs/03-solution/reference-design/design-job-task-engine.md`。
- 证据来源：源码静态核对、`uv` 命令验证、隔离 smoke、现有单测与集成测试文件。

## 2. 已满足或基本满足的设计点

| 领域 | 结论 | 证据 |
|---|---|---|
| Task Engine V2 的共享执行内核 | 已实现 | `ExecutionRunner` 已从 Dispatcher 中抽出，并统一承担环境获取、上下文注入、hooks 和清理流程，见 `src/core/atm/execution_runner.py` 与 `src/core/atm/dispatcher.py` |
| Job Controller 的 crash recovery | 已实现 | `src/core/atm/controller.py` 启动时会恢复僵尸任务并清理残留环境 |
| 外部模块打包安装主链路 | 已实现 | 内置业务模块已删除；`ModuleRegistry.install()` + `ModuleService` 已可从外部 zip 安装并加载模块；隔离 smoke 已验证安装后从应用受控目录加载 |
| 调试会话采用 Core 真实执行链 | 基本满足 | `DebugService`、worker 进程、`ExecutionRunner` 和 dev-link 调试路径已经落地，整体方向与 `DBG-01` 设计一致 |

## 3. 当前结论与剩余差距

### 3.1 已在本轮关闭的问题

- `BUG-002`：已恢复 `src.automation.*` 兼容路径，打包模块 smoke 已确认 `labor_workflow` 不再因缺少旧导入而退化。
- `BUG-003`：`uv run pytest -q` 与 `uv run python scripts/smoke_test_ui.py` 当前都已恢复通过。
- `BUG-004`：`_install_from_zip()` 已改为临时目录校验 + 备份旧目录 + 原子替换，回归测试已覆盖旧文件不残留。
- `BUG-005`：`hybrid` 已从策略模型与编辑器中移除，并补充了对应回归测试。

### 3.2 `CR-003` MMS 的 settings store 与 UI 扩展合规实现仍未闭环

- 严重级别：P1
- 设计影响：MMS 已补齐 settings store 与模块状态持久化，但 UI 加载与 trust gate 仍未闭环
- 证据：
  - `src/core/mms/settings_store.py` 已提供模块级/工作流级 settings、导出与模块状态持久化
  - `src/core/mms/registry.py` 已在 reload/install/uninstall 路径中应用模块状态持久化
  - `src/core/mms/ui/module_detail_page.py` 对自定义模块页面仍停留在 `TODO` 和占位页；除 `core:data_table:*` 外不会真正加载模块提供的 UI
  - 当前代码中没有看到 `trusted` / allowlist / 白名单门控被实际执行
- 结论：MMS 已具备配置基础设施，但 UI Host 仍未达到 SRS/设计对受信 micro-app 装载的完整要求

## 4. 当前验证结果摘要

| 项目 | 结果 | 说明 |
|---|---|---|
| `uv run pytest -q` | 通过 | `184 passed` |
| Docs markdown tree | 通过 | `docs/` 已统一为单一 Markdown 文档树 |
| `uv run ruff check .` | 通过 | 维护范围代码与常规自动化测试已通过；历史人工脚本不计入默认 gate |
| `uv run python scripts/smoke_test_ui.py` | 通过 | `QApplication` 与 `Shell` 初始化均成功 |
| 外部模块安装 smoke | 通过 | 安装 zip 后可从应用受控目录发现并加载模块 |
| `ctrip labor_workflow` 外部安装 smoke | 通过 | 已进入真实执行链，不再因旧导入缺失而退化 |

## 5. 额外观察

- 调试链路集成测试已改为使用仓内生成的临时模块，不再依赖当前机器上固定存在外部源码目录。

## 6. 结论

- `TASK-008` 的目标已完成：当前仓库已有可回溯的“已满足 / 未满足 / 风险”清单。
- 项目仍处于 `IMPLEMENTATION`，当前主要剩余差距集中在 MMS 高阶合规能力。
- `TASK-011` 已完成，后续如继续推进，应直接执行 `TASK-012`。
