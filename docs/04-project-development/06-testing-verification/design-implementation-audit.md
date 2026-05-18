# 设计与实现一致性审查

**项目名称：** 蛛行演略（crawler4j）
**文档状态：** 已批准
**负责人：** 当前仓库维护者
**主要读者：** Tech Lead | Dev | QA | 发布负责人
**上游输入：** 当前代码 | 当前命令验证结果 | 当前正式文档
**下游输出：** `.factory/workitems/` | `.factory/memory/current-state.md`
**关联 ID：** `TASK-008`, `TASK-003`, `TASK-009`, `CR-003`
**最后更新：** 2026-04-22

## 1. 审查范围与方法

- 审查范围：MMS、ATM/Task Engine、Debug Session、模块外部安装链路、质量门。
- 对照输入：当前方案设计文档、当前代码与可重复验证结果。
- 证据来源：源码静态核对、`uv` 命令验证、隔离 smoke、现有单测与集成测试文件。

## 2. 已满足或基本满足的设计点

| 领域 | 结论 | 证据 |
|---|---|---|
| Task Engine V2 的共享执行内核 | 已实现 | `ExecutionRunner` 已从 Dispatcher 中抽出，并统一承担环境获取、上下文注入、workflow 执行、对象 `setup(ctx, workflow)` / `cleanup(ctx, outcome)` 触发和环境回收收口，见 `packages/crawler4j/src/core/atm/execution_runner.py`、`packages/crawler4j/src/core/mms/service.py` 与 `packages/crawler4j/src/core/mms/object_container_v2.py` |
| Job Controller 的 crash recovery | 已实现 | `packages/crawler4j/src/core/atm/controller.py` 启动时会恢复僵尸任务并清理残留环境 |
| 外部模块打包安装主链路 | 已实现 | 内置业务模块已删除；`ModuleRegistry.install()` + `ModuleService` 已可从外部 zip 安装并加载模块；隔离 smoke 已验证安装后从应用受控目录加载 |
| 调试会话采用 Core 真实执行链 | 基本满足 | `DebugService`、worker 进程、`ExecutionRunner` 和 dev-link 调试路径已经落地，整体方向与 `DBG-01` 设计一致 |

## 3. 当前结论与剩余差距

### 3.1 已在本轮关闭的问题

- `BUG-002`：旧 `src.automation.*` 兼容包已删除；模块执行统一回到 MMS + ModuleAssembler 正式链路。
- `BUG-003`：`uv run pytest -q` 与 `uv run python scripts/smoke_test_ui.py` 当前都已恢复通过。
- `BUG-004`：`_install_from_zip()` 已改为临时目录校验 + 备份旧目录 + 原子替换，回归测试已覆盖旧文件不残留。
- `BUG-005`：`hybrid` 已从策略模型与编辑器中移除，并补充了对应回归测试。

### 3.2 `CR-003` / `CR-011` 当前结论

- `packages/crawler4j/src/core/mms/settings_store.py` 已提供模块级/工作流级 settings、导出与模块状态持久化
- 旧 `CR-003` 范围已停留在历史完成态；后续 2026-04-22 又以 `CR-011` 把模块 UI 正式切到 hosted page V1
- `packages/crawler4j/src/core/mms/ui_loader.py`、trust gate / allowlist 与 `ui:*` 实时加载路径已从正式实现中移除
- `packages/crawler4j/src/core/mms/ui/module_detail_page.py` 现在只消费 `core:page:<page_id>` 与 `core:data_table:<view_id>`，由宿主 `ManagedPageRenderer` 渲染 hosted page
- `packages/crawler4j/tests/unit/test_core/test_mms/test_module_detail_page.py`、`test_managed_page_renderer.py` 与 SDK / integration / acceptance 回归已覆盖 hosted page 契约

## 4. 当前验证结果摘要

| 项目 | 结果 | 说明 |
|---|---|---|
| `uv run pytest -q` | 通过 | `188 passed` |
| Docs markdown tree | 通过 | `docs/` 已统一为单一 Markdown 文档树 |
| `uv run ruff check .` | 通过 | 维护范围代码与常规自动化测试已通过；历史人工脚本不计入默认 gate |
| `uv run python scripts/smoke_test_ui.py` | 通过 | `QApplication` 与 `Shell` 初始化均成功 |
| 外部模块安装 smoke | 通过 | 安装 zip 后可从应用受控目录发现并加载模块 |
| `ctrip labor_workflow` 外部安装 smoke | 通过 | 已进入真实执行链，不再因旧导入缺失而退化 |

## 5. 额外观察

- 调试链路集成测试已改为使用仓内生成的临时模块，不再依赖当前机器上固定存在外部源码目录。

## 6. 结论

- `TASK-008` 的目标已完成：当前仓库已有可回溯的“已满足 / 未满足 / 风险”清单。
- 项目仍处于 `IMPLEMENTATION`，当前主要剩余差距已收敛到真实站点 E2E 与发布收口。
- `CR-003` 已关闭；如继续推进，更适合转向 `ctrip` 真实站点回放或 release prep。
