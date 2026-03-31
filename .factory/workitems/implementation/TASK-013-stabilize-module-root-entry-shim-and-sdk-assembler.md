# TASK-013 统一模块根入口为最新托管方案并要求模块重新初始化

- 状态：DONE
- 负责人：Gemini
- 优先级：P1
- 估算：1.5 人/天
- 关联 ID：`TASK-013`, `REQ-003`, `REQ-006`, `NFR-004`

## 目标

- 让新模块的根 `__init__.py` 成为稳定托管薄壳，避免模块开发者继续手工维护该文件
- 将默认任务/工作流发现与模块级入口组装逻辑沉淀到 SDK helper 中
- 保持当前 Core 继续从根 `__init__.py` 加载模块
- 将旧模块升级路径统一为按最新模板重新初始化，而不是兼容旧模板

## 范围

- 在 `crawler4j_sdk` 中新增统一模块入口组装 helper
- 将 `init-model` 模板切换为固定薄壳 `__init__.py`
- 约定可选 `module_runtime.py` 作为模块级可变运行时扩展位置
- 明确旧模块的重初始化步骤与迁移清单
- 补齐相关测试与文档

## 非目标

- 不修改 Core 当前“根 `__init__.py` + `module.yaml`”加载契约
- 不为旧式完整 `__init__.py` 模板提供兼容承诺
- 不实现 AST 级自动改写工具

## 验收标准

- CLI 新生成的模块根 `__init__.py` 为固定薄壳
- SDK helper 能提供默认的任务/工作流发现与 `run(context)` 分发逻辑
- 模块级自定义 hooks / `DEFAULT_WORKFLOW` 可通过 `module_runtime.py` 覆盖
- 文档明确旧模块必须按最新模板重新初始化
- 存在针对 shim、新扩展点和重初始化产物的回归测试
- 正式文档、追踪矩阵和 `.factory/memory/` 已同步
