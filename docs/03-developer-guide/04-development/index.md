# 04 模块开发概览

本目录收纳 TaskScript、Workflow、CLI/UI 配置和 Core 能力说明。
这里的所有宿主扩展示例都以 `ctx.tools.call(...)` 统一工具接口为准，旧 `DataService` 和 `ctx.db` 专用字段口径都不再适用。

建议阅读顺序：

1. 4.1 编写 TaskScript
2. 4.2 编写 Workflow
3. 4.3 CLI 命令与 UI 配置
4. 4.4 Core 提供的能力清单
5. [4.5 Core 注入能力 API 参考 (SDK 1.1.0)](05-api-reference.md)
6. [4.6 模块开发最佳实践](06-best-practices.md)
