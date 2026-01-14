---
trigger: always_on
---

# Crawler4j 项目最高宪法 (Project Constitution)

> **生效范围**：所有 AI 生成的代码、建议、文档及架构决策。
> **核心哲学**：微内核架构、严格的依赖管理、异步驱动。

## 1. 元规则 (Meta-Rules) - 绝对红线

任何违反以下规则的代码将被视为无效：

1. **包管理霸权 (uv Only)**
* **严禁** 使用 `pip`、`poetry` 或 `conda`。
* **命令规范**：
* 运行脚本：`uv run python <script>`
* 添加依赖：`uv add <package>` (涉及 dev 依赖加 `--dev`)
* 环境同步：`uv sync`


* **AI 行为**：当需要安装库时，直接给出 `uv add` 命令，**不要询问**用户偏好。


2. **技术栈锁定**
* **Python 版本**：严格锁定 `3.12+`，鼓励使用最新的 Type Hinting 语法（如 `type Alias = ...`）。
* **异步模型**：核心逻辑必须基于 `asyncio`。禁止在核心流程中使用同步阻塞 I/O（除非是文件系统操作且无异步替代方案）。
* **GUI 框架**：PyQt6。必须配合 `qasync` 实现事件循环整合。

---

## 2. 架构边界法案 (Architecture Boundaries Act)

为了防止架构腐化，必须严格遵守以下依赖方向：

1. **模块隔离原则 (Module Isolation)**
* 位置：`modules/<module_name>/`
* **禁止项**：业务模块代码 **严禁 import** `src` 目录下的任何内容。
* **正确做法**：必须且只能通过 `crawler4j_sdk` 提供的 `TaskContext` 与宿主环境交互。
* **理由**：确保插件可插拔，核心框架升级不破坏现有插件。


2. **核心极简原则 (Micro-kernel Core)**
* 位置：`src/core/`
* **职责**：仅负责生命周期管理 (MMS)、任务调度 (TSM)、环境分配 (REM)。
* **禁止项**：核心层 **严禁包含** 特定业务逻辑（如“登录携程”、“解析淘宝页面”）。这些必须下沉到 Modules。


3. **SDK 契约原则 (SDK Contract)**
* 位置：`crawler4j_sdk/`
* **稳定性**：SDK 是公开 API。修改 `TaskContext` 或 `TaskScript` 基类必须保证**向后兼容**。
* **独立性**：SDK 不能依赖 `src/` (循环依赖死罪)。

---

## 3. UI/UX 开发法案 (Interface Guidelines)

针对桌面端应用的特殊约束：

1. **主线程神圣不可侵犯**
* **严禁** 在 UI 线程（Main Thread）中执行 `requests.get`、`time.sleep` 或繁重的计算。
* **必须** 使用 `async def` 配合 `qasync.asyncSlot`，或将任务派发到 `QThread`/`Worker`。


2. **组件通信规范**
* UI 组件与后台逻辑解耦，必须通过 **Signals & Slots (信号与槽)** 机制通信。
* 禁止 UI 直接调用后台对象的同步方法并等待返回值（这会导致界面卡死）。

---

## 4. 开发工作流 (Development Protocols)

1. **文档驱动 (Documentation First)**
* 在修改架构或关键接口前，必须先更新 `docs/` 下的对应文档。
* 代码中的 Docstring 必须与 `docs/sdk/api.md` 保持一致。


2. **错误处理 (Error Handling)**
* **SDK 层**：捕获底层的 `Playwright` 异常，封装为 `SDKError` 抛出，不要暴露底层堆栈给插件开发者。
* **Module 层**：任务失败时不应直接抛出异常导致崩溃，应返回 `TaskResult.fail(error=...)`。

---
## 5. AI 角色行为准则 (Persona Instructions)

* **当你编写 Module 时**：假装你看不见 `src/` 目录，只知道 `crawler4j_sdk` 的存在。
* **当你编写 Core 时**：假装你不知道具体的业务是什么，只关注调度通用任务。
* **当你编写 UI 时**：假装每一个按钮点击都可能耗时 10 秒，必须设计 Loading 状态。