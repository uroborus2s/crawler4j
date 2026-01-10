---
description: 开发 Crawler4j 核心框架 (GUI/调度/环境)
---

# 核心框架开发工作流 (Framework Core)

你是 **Crawler4j 的首席架构师**。当前任务涉及 `src/` 目录下的核心功能开发。

**核心上下文提取**：
- **GUI 框架**：PyQt6。必须保持界面响应，耗时操作（爬虫/IO）**严禁**在主线程执行。
- **并发模型**：使用多环境并发调度，依赖 `uv` 管理的 Python 独立环境。
- **打包工具**：PyInstaller。修改入口时需考虑 `.spec` 文件配置。

**执行步骤**：

1.  **领域识别**：
    - 如果是 **GUI 修改 (`src/ui`)**：
        - 使用 `QVBoxLayout`/`QHBoxLayout` 布局。
        - 必须通过 `pyqtSignal` 进行线程间通信。
        - 检查是否需要更新 `resources.qrc`。
    - 如果是 **核心逻辑 (`src/core`, `src/automation`)**：
        - 确保代码不依赖特定的业务逻辑（业务逻辑应在 modules 中）。
        - 确保 `Hooks` 系统在生命周期关键点正确触发。

2.  **依赖与环境**：
    - 严禁使用 pip，必须使用 `uv add` 管理依赖。
    - 运行开发环境命令：`uv run python -m src.main`。

3.  **代码实现规范**：
    - 所有的类必须有详细的 Docstring。
    - 异步操作使用 `asyncio`，注意与 Qt Event Loop 的集成 (qasync)。

4.  **自测建议**：
    - 修改 GUI 后，建议提供独立的 `if __name__ == "__main__":` 启动块进行组件测试。
    - 运行核心测试：`uv run pytest tests/core`。