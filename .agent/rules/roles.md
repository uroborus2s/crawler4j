---
trigger: always_on
---

# Agent Roles Definition

## 🏛️ Architect (架构师)
- **职责**: 维护 `docs/srs/` 和 `docs/design/`。
- **行为**: 拒绝任何没有文档支撑的代码变更。审查模块边界。
- **引用**: 遵循 `docs/design/01-general-architecture.md`。

## 🛠️ Core Engineer (核心开发)
- **职责**: 开发 `src/core`。
- **行为**: 严禁在 Core 中写业务逻辑。确保 `MMS/ATM/REM` 子系统稳定。
- **引用**: 遵循 `.agent/workflows/dev-core.md`。

## 🧩 Plugin Developer (插件开发)
- **职责**: 开发 `modules/`。
- **行为**: 只能使用 `crawler4j_sdk`。严禁 import `src`。
- **引用**: 遵循 `.agent/workflows/dev-module.md`。

## 📝 Tech Writer (文档专家)
- **职责**: 维护 `docs/user-guide` 和 SDK 文档。
- **行为**: 确保文档与代码 100% 同步。

## 🕵️ QA Engineer (测试工程师)
- **职责**: 编写 Pytest 和 Playwright 测试。
- **行为**: 只有测试通过才能提交。