---
trigger: always_on
---

## 1. 项目概览
**Crawler4j** 是一个自动化监控与任务执行平台
1. **核心技术**: Python 3.12+, Asyncio, Type Hinting.
2. **架构原则**: 微内核 (Micro-kernel) + SDK + 插件 (Plugins/Modules)。
   - **Framework Core (微内核)**: 负责生命周期管理、调度、配置加载、事件总线，保持极简。
   - **SDK**: 提供给开发者使用的标准接口、上下文对象（Context）、工具链，屏蔽内核复杂性。
   - **Modules (插件)**: 具体的业务逻辑实现（如特定网站的爬虫、特定的监控逻辑、数据存储适配器等），通过 SDK 与内核交互。

## 2. 环境与包管理 (严格执行)
本项目使用 **uv** 进行全生命周期管理。**禁止使用 pip**。
- **运行脚本**：始终使用 `uv run python <script.py>`。
- **添加依赖**：使用 `uv add <package>`。
- **同步环境**：如果环境不一致，建议运行 `uv sync`。
- **Python 版本**：限制为 `3.12+`。


**AI 交互指令**：
如果涉及依赖变更，直接给出 `uv add` 命令，不要问我是否使用 pip。