# 头脑风暴记录：模块根 `__init__.py` 自动托管改造

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 草稿  
**负责人：** 当前仓库维护者  
**主要读者：** 架构 | 开发 | QA | 模块开发者  
**上游输入：** 用户关于模块根 `__init__.py` 是否应由工具维护的讨论 | `docs/03-developer-guide/03-project-structure/01-layout-and-entrypoints.md` | `packages/crawler4j-sdk/src/cli/templates.py` | `packages/crawler4j/src/core/mms/service.py`  
**下游输出：** `docs/04-project-development/03-requirements/prd.md` | `docs/04-project-development/03-requirements/requirements-analysis.md` | `docs/04-project-development/04-design/module-boundaries.md` | `docs/04-project-development/04-design/api-design.md` | `docs/04-project-development/05-development-process/implementation-plan.md` | `.factory/workitems/implementation/TASK-013-stabilize-module-root-entry-shim-and-sdk-assembler.md`  
**关联 ID：** `REQ-003`, `REQ-006`, `TASK-013`  
**最后更新：** 2026-03-31  

## 1. 问题背景

- 当前 `init-model` 会生成完整的模块根 `__init__.py`，其中同时包含自动发现、默认工作流、任务/工作流调度以及默认 hooks 模板。
- 这意味着根 `__init__.py` 虽然是脚手架生成的，但它仍然承载可变运行时逻辑；一旦 SDK 模板升级、默认工作流调整或模块作者需要自定义 hooks，就容易回到人工维护。
- Core 当前仍然通过模块根 `__init__.py` 加载模块；因此本轮不能简单删除该文件或要求 Core 直接改为别的入口契约。

## 2. 设计目标

- 让模块开发者在常规开发中不再手工维护根 `__init__.py`。
- 保持当前 Core 加载契约不变，避免同时改动 SDK、模块模板和宿主加载链的多个高风险点。
- 收敛到单一新模板口径；旧模块升级时统一按最新方式重新初始化，不再为旧模板保留兼容承诺。

## 3. 备选方案

| 方案 | 做法 | 优点 | 缺点 |
|---|---|---|---|
| A. CLI 持续重写根 `__init__.py` | 每次 `add-workflow`、`add-ui` 等命令后重新生成根入口 | 现有模型改动最小 | 容易覆盖人工改动；模板升级冲突大；对已有模块很难安全合并 |
| B. 稳定薄壳 + SDK 组装器 + 重初始化升级 | 根 `__init__.py` 固化为极薄 shim，真正的默认运行逻辑由 SDK helper 提供，可选自定义逻辑放到独立文件；旧模块升级时直接重建骨架 | 不需要改 Core；后续几乎无需维护根入口；口径单一 | 旧模块升级要重初始化并搬运业务代码 |
| C. Core 直接按 manifest 声明加载 | Core 不再要求根 `__init__.py`，改由 `module.yaml` 指定运行入口 | 长期最干净 | 需要修改宿主契约、扫描器、模块模板与历史模块；本轮改动面过大 |

## 4. 选型结论

推荐方案 B。

原因：

- 它保留了当前最稳定的宿主事实：模块根目录必须包含 `module.yaml` 和根 `__init__.py`。
- 它把“需要持续演化的逻辑”从模块根入口文件中抽走，后续 SDK 升级时只改一处。
- 它允许项目收敛到单一最新模板；旧模块的升级路径统一为重新初始化，而不是继续兼容旧写法。

## 5. 最小改造设计

### 5.1 根入口文件职责收缩

模块根 `__init__.py` 收敛为固定薄壳，只负责从 SDK 导出标准入口：

```python
from crawler4j_sdk.module_entry import export_entrypoints

globals().update(export_entrypoints(__name__, __file__))
```

设计意图不是“继续由工具频繁改写 `__init__.py`”，而是“把它变成几乎永远不需要再改的托管壳文件”。

### 5.2 SDK 统一入口组装器

在 `crawler4j_sdk` 中新增模块入口 helper，例如 `crawler4j_sdk.module_entry.export_entrypoints(package_name, package_file)`，负责：

1. 定位模块根目录
2. 自动扫描 `tasks/` 与 `workflows/`
3. 生成默认 `run(context)` 分发逻辑
4. 暴露默认 no-op hooks
5. 加载可选的模块级扩展文件

### 5.3 模块级可变逻辑迁移位置

新增一个可选的模块级文件，例如 `module_runtime.py`，承载真正允许开发者自定义的内容：

- `run(context)`
- `prepare_env`
- `init_env`
- `before_run`
- `on_success`
- `on_failure`
- `on_timeout`
- `on_cleanup`
- `DEFAULT_WORKFLOW`

当 `module_runtime.py` 不存在时，使用 SDK 的默认实现；当其存在并导出同名对象时，以模块本地实现覆盖 SDK 默认值。

### 5.4 默认工作流解析规则

为避免再把默认工作流写死在根 `__init__.py`，默认工作流按以下顺序解析：

1. `context.get_config("workflow")`
2. `module_runtime.py.DEFAULT_WORKFLOW`
3. `module.yaml.workflows[0].name`

这样 `add-workflow` 继续只需要维护 `module.yaml`，新模块的根 `__init__.py` 无需再同步。

## 6. 边界与升级方式

### 6.1 本轮明确包含

- 新增 SDK helper
- 更新 `init-model` 脚手架模板
- 明确旧模块的升级路径为按最新模板重新初始化
- 增补设计、开发者文档与测试计划

### 6.2 本轮明确不做

- 不修改 Core “必须从根 `__init__.py` 进入模块”的当前契约
- 不为旧式完整 `__init__.py` 模板提供兼容承诺
- 不做 AST 级自动迁移工具
- 不引入新的复杂 manifest 字段

## 7. 建议的实施切片

1. 在 SDK 中落地统一入口组装器
2. 将 CLI 模板切换为稳定薄壳 `__init__.py`
3. 增加 `module_runtime.py` 可选约定与重新初始化说明
4. 更新开发者文档、需求追踪和测试计划

## 8. 主要风险

| 风险 | 表现 | 控制方式 |
|---|---|---|
| 旧模块需要重初始化 | 现有模块作者需要重建骨架并迁移业务代码 | 提供清晰的重初始化步骤与最小迁移清单 |
| 默认工作流来源变更 | 开发者误以为仍由根 `__init__.py` 控制 | 在文档中明确解析顺序，并让 CLI 继续维护 `module.yaml` |
| 动态加载错误更难排查 | `module_runtime.py` 导入失败时表现为运行时异常 | 设计时要求 helper 输出清晰错误信息，并保留最小 smoke 覆盖 |

## 9. 决策输出

- 新增 `REQ-006`，把“模块根入口应可由工具托管、开发者不再手工维护”上升为正式需求。
- 新增 `TASK-013`，作为后续待确认后实施的最小实现任务。
- 旧模块不再作为兼容目标；进入实施时统一按最新模板重新初始化。
- 当前不直接改代码；待用户确认后，再按本设计进入实现闭环。
