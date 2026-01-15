---
description: 架构方案设计 (Architecture Design)
---

**触发条件**: 用户要求"设计新功能"、"出技术方案"或"架构评审"。

**前置检查 (Pre-Flight Check)**
* **必须阅读**: `docs/design/01-general-architecture.md` (总体架构)
* **必须阅读**: `docs/srs/04-architecture.md` (依赖边界)

**阶段一：架构定位 (角色: @技术文档专家)**
1.  **功能归属分析**:
    * 判断该功能属于 **Core** (通用治理/资源管理)、**SDK** (契约/接口) 还是 **Module** (具体业务/抓取逻辑)。
    * *判据*: 如果包含具体网站（如携程）的逻辑，**必须** 归入 Module。如果涉及任务调度算法，归入 Core。
2.  **依赖方向检查**:
    * 确保依赖流向为 `Modules -> SDK -> Core`。
    * **红线**: 严禁 Module 代码引用 `src.core` 内部包。

**阶段二：详细设计 (角色: @首席架构师)**
1.  **API 契约定义**:
    * 若需修改 SDK，定义 `TaskContext` 或 `TaskResult` 的变更，确保向后兼容。
2.  **数据流设计**:
    * 定义数据如何落地。业务数据应通过 `ctx.emit` 存入 `Data Store`，状态数据存入 `State Store` (KV)。
3.  **并发与异步模型**:
    * 设计必须基于 `asyncio`。
    * UI 交互必须通过 Signal/Slot 或 EventBus 解耦，严禁阻塞主线程。

**阶段三：产出交付**
1.  **编写文档**: 在 `docs/design/` 下创建设计文档（如 `design-feature-xyz.md`）。
2.  **内容包含**:
    * 修改文件列表预估。
    * 核心类图/时序图 (Mermaid)。
    * **架构合规性声明**: 显式列出是否触犯架构红线。