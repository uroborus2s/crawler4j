---
description: 将多个角色串联起来的“指挥棒”
---

# Workflow: Feature Development Cycle

## Trigger
User says: "开发一个新功能..."

## Steps
1. **Phase 1: Design (Arch-Reviewer)**
   - 分析需求，更新 `docs/srs/`。
   - 检查是否需要修改 SDK 契约。

2. **Phase 2: Contract (SDK-Maintainer)**
   - 如果 Phase 1 指出需要 SDK 变更，先修改 SDK 并发布版本。
   - 更新 `docs/sdk/api.md`。

3. **Phase 3: Implementation (Kernel/Plugin/UI)**
   - 根据功能归属，切换到对应角色进行编码。
   - **Constraint**: 必须遵守 `.agent/rules/crawler4j-rules.md` 中的依赖红线。

4. **Phase 4: Verification (Skills)**
   - 运行 `uv run pytest`。
   - 如果是插件，调用 `@run-plugin-debug` 进行验证。

5. **Phase 5: Documentation**
   - 更新 `README.md` 或 `docs/user-guide`。