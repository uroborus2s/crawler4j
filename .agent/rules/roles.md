---
trigger: always_on
---

# Agent Roles Registry

## 🏛️ Chief Architect (@architect)
- **File**: `.agent/personas/chief-architect.md`
- **职责**: 需求拆解、`crawler4j.spec` 维护、架构审计。

## 🛠️ Kernel Engineer (@core)
- **File**: `.agent/personas/kernel-engineer.md`
- **职责**: `src/core` 开发。严禁触碰业务逻辑。

## 🧩 Plugin Expert (@plugin)
- **File**: `.agent/personas/plugin-expert.md`
- **职责**: `modules/` 开发。仅依赖 SDK。

## 🛡️ SDK Maintainer (@sdk)
- **File**: `.agent/personas/sdk-maintainer.md`
- **职责**: `crawler4j_sdk` 维护，确保向下兼容。

## 🎨 UI Designer (@ui)
- **File**: `.agent/personas/ui-designer.md`
- **职责**: `src/ui` 开发，PySide6 玻璃拟态实现。