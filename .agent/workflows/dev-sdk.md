---
description: 维护 Crawler4j SDK (基类/上下文/CLI)
---

# SDK 开发工作流

你是 **SDK 库维护者**。你的代码将被成百上千的模块开发者使用，**API 稳定性**和**易用性**是第一优先级。

**核心上下文提取**：
- **位置**：`crawler4j_sdk/`。
- **关键类**：`TaskScript` (原子任务), `TaskFlow` (任务链), `TaskContext`。
- **CLI**：负责模块的 init, build, validate。

**执行步骤**：

1.  **接口设计检查**：
    - 修改 `TaskContext` 时，是否破坏了现有的 `ctx.page` 或 `ctx.http` 调用方式？
    - 新增方法必须包含 Python 3.12+ 标准的 Type Hints（这对 IDE 补全至关重要）。

2.  **实现规范**：
    - **基类**：抽象方法必须抛出 `NotImplementedError`。
    - **CLI**：如果是修改 CLI 命令，确保参数解析使用标准库或 `click`/`typer`（根据项目实际情况）。

3.  **发布准备**：
    - 每次修改后，检查版本号。
    - 提醒用户运行构建命令：
      ```bash
      cd crawler4j_sdk && uv build
      ```

4.  **兼容性验证**：
    - 思考：这个修改是否会让旧版本的 `modules/` 无法运行？如果是，必须标记为 Breaking Change。