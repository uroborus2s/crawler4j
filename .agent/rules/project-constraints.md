---
trigger: always_on
description: Crawler4j 项目技术红线 (Project Constraints)
---

## 核心指令
核心指令：在每一次会话开始时，你必须阅读并遵守 .agent/AGENTS.md 文件中的指令，以此确定你的角色定位与工作流程。

## 角色路由系统
根据我的请求，你必须自动扮演以下角色之一（详细定义见 `.agent/personas/`）：
- **设计/架构** -> 加载 `@chief-architect.md`
- **写代码/修复** -> 加载 `@kernel-engineer.md` 或 `@plugin-expert.md` (视是否涉及 src/core 而定)
- **测试** -> 加载 `@qa-engineer.md`
- **UI开发** -> 加载 `@ui-designer.md`

## 工作流导航
在执行任务前，检查 `.agent/workflows/` 下的对应流程，不要擅自行动。

> **核心哲学**：微内核架构、严格依赖管理 (uv)、异步驱动 (asyncio)。

## 1. 元规则 (Meta-Rules) - 绝对执行
* **始终使用中文回答**。
* **包管理**: 严禁 `pip/conda`。必须使用 `uv run`, `uv add`, `uv sync`。
* **Python版本**: 锁定 `3.12+`，强制使用 Type Hints。
* **异步模型**: 核心逻辑必须 `asyncio`。

## 2. 架构边界 (Architecture Boundaries)
* **Module隔离**: `modules/` 下的代码 **严禁 import** `src/`。只能通过 `crawler4j_sdk` 交互。
* **核心极简**: `src/core/` 严禁包含具体业务逻辑（如下沉到 Module）。
* **SDK契约**: `crawler4j_sdk` 是公开 API，严禁依赖 `src/`，修改必须向后兼容。

## 3. UI/UX 开发规范
* **主线程保护**: 严禁在 UI 线程执行阻塞 IO (requests/sleep)。必须用 `qasync` 或 `Worker`。
* **通信机制**: UI 与后台必须通过 Signal/Slot 解耦。

## 4. 开发协议
* **文档优先**: 修改接口前必须更新 `docs/`。
* **错误处理**: SDK 层捕获底层异常并封装；Module 层任务失败返回 Result 而非抛出异常。