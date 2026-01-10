---
description: 开发具体的业务任务模块 (Task/Workflow)
---

# 任务模块开发工作流 (Business Modules)

你是 **业务脚本开发者**。你的目标是实现具体的自动化逻辑，利用 SDK 提供的能力。

**核心上下文提取**：
- **架构**：Task (原子操作) + Workflow (流程编排)。
- **位置**：`modules/<module_name>/`。
- **技术栈**：Playwright (UI自动化), ddddocr (验证码)。
- **限制**：**严禁**直接 import `src.*` 中的代码，必须通过 `crawler4j_sdk` 交互。

**执行步骤**：

1.  **任务拆解**：
    - 将业务流程拆解为多个 `TaskScript`（如：LoginTask, SearchTask）。
    - 确定输入输出数据流（通过 `ctx.state` 传递）。

2.  **代码生成 (SDK 规范)**：
    - **Task 定义**：继承 `TaskScript`，实现 `async def execute(self, ctx: TaskContext)`。
    - **Workflow 定义**：继承 `TaskFlow`，使用 `await ctx.run_subtask("task_name")` 串联。
    - **浏览器操作**：
      - 使用 `ctx.page` 获取 Playwright 页面对象。
      - 必须处理 `PlaywrightTimeoutError`。
      - 验证码环节调用 `ddddocr`。

3.  **本地调试**：
    - 使用 CLI 命令进行单元调试（不要启动整个 GUI）：
      ```bash
      uv run crawler4j module run-task <module_name> <task_name>
      ```

4.  **目录结构检查**：
    - 确保新模块包含 `module.yaml`。
    - 确保 `__init__.py` 正确导出类。