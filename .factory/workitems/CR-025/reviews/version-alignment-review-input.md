# TASK-045 版本增量复评输入

- 范围：用户在实现复评通过后新增的公共契约 patch 版本要求。
- 目标：Contracts `0.4.5`、SDK `0.4.6`；SDK/Core 最低 Contracts `>=0.4.5,<0.5.0`；模板、README、正式版本文档、lock 和项目版本事实一致。
- 产物：`packages/crawler4j-contracts/pyproject.toml`、`packages/crawler4j-sdk/pyproject.toml`、`packages/crawler4j/pyproject.toml`、`uv.lock` 及相关文档/测试。
- 验证：packaging GREEN `65 passed`；最终目标集含 packaging `320 passed`；full unit `1287 passed`；两包 build、wheel METADATA 与 Contracts wheel 隔离公开导入通过。
- 发布语义：源码版本已提升但本轮不发布；正式版本文档必须同时保留当前源码版本与既有 PyPI 发布版本。

Reviewer 只读，不修改文件；只需检查新增版本增量是否完整、一致并报告阻断问题或批准。
