# 环境候选异步与候选上下文需求简报

- 项目：crawler4j
- Work item：`CR-025`
- 任务：`TASK-045`
- 状态：`requirements_ready`
- 场景：`add_requirement`
- 来源：用户提供的已确认通用契约与验收口径
- 日期：2026-08-08
- 目标协议：Core `0.4.0` / `core-native-v2`
- analysis_mode：`embedded`
- analysis_locator：本文“需求分析”章节

## 目标

让模块在环境选择前通过同步或异步 `@env_candidates` 计算候选，并可把同一次计算产生的 JSON-safe 上下文传给最终选中环境对应的 workflow。

## 需求

- `REQ-017`：`@env_candidates` 接受同步或异步函数；Core 对返回的 awaitable 只调用一次并正确 await，旧同步函数保持兼容。
- `REQ-018`：候选函数可返回现有 `EnvCandidates` / env id 集合，或返回“候选集合 + context”的公开 Contracts 结果类型。
- `REQ-019`：Core 选定环境后，把同一次候选结果中的 context 注入 workflow `TaskContext`；不得为取得 context 再次执行候选函数。
- `REQ-020`：SDK scanner、manifest lock、类型导出、脚手架说明和 Core/SDK/Contracts README 同步支持异步候选；环境清理候选仍为同步纯函数。
- `REQ-021`：公开新符号不得沿用已发布旧版本；Contracts 源码提升到 `0.4.5`，SDK 源码提升到 `0.4.6` 且最低依赖 Contracts `0.4.5`，同步锁文件、版本文档和打包一致性测试。本轮不发布。
- `REQ-022`：承载 Core 新运行能力的根应用 / 客户端源码 patch 版本提升到 `0.4.41`，同步根包元数据、lock、README、版本治理、发布文档和项目事实。本轮不发布客户端资产。
- `NFR-015`：context 必须可安全 JSON 序列化、拒绝非有限数字，并限制为 64 KiB UTF-8 JSON；错误不得输出 context 内容。

## 验收标准

- `AC-025-001`：同步候选继续返回原列表行为；异步候选被 await 且单次解析只调用一次。
- `AC-025-002`：结构化候选的 context 精确出现在选中 workflow 的 `TaskContext.candidate_context`。
- `AC-025-003`：无 context、固定 `env_id`、创建环境路径的 `candidate_context` 为 `None`；候选为空时不运行 workflow，context 不保留。
- `AC-025-004`：候选异常、超时、非法或过大 context 沿用资源获取失败/等待语义，不记录 context 内容。
- `AC-025-005`：SDK 扫描、manifest lock、打包校验接受异步 `@env_candidates`，且仍拒绝异步 `@env_cleanup_candidates`。
- `AC-025-006`：单元、集成、验收测试覆盖同步兼容、异步 await、结构化 context、空候选、异常、固定 env_id 和 manifest 扫描。
- `AC-025-007`：Contracts/SDK 包元数据、SDK 依赖、脚手架生成范围、README、版本治理与 `uv.lock` 一致指向 `0.4.5` / `0.4.6`；最终报告明确外部模块最低版本。
- `AC-025-008`：根应用包元数据、运行时版本、README、版本治理、发布文档、项目事实和 `uv.lock` 一致指向 `0.4.41`，并完成 root wheel/sdist 构建。

## 非目标

- 不修改 `ctrip_crawler`。
- 不实现城市阈值、账号永久绑定或异城三次退出等业务规则。
- 不让候选函数拥有浏览器或环境写入能力；仅开放已有宿主管理的异步 HTTP 工具与只读模块数据。
- 不扩展 `@env_cleanup_candidates` 的返回结构或异步能力。

## 需求分析

- 领域映射：Contracts 公共类型与 `TaskContext`、SDK 静态扫描/manifest、Core MMS 调用与 ATM 环境选择。
- 接口 owner：Contracts 定义公开返回类型和上下文字段；Core 校验、选择和注入；SDK 只做静态识别与文档/manifest 产出。
- 兼容策略：旧返回值和同步调用返回值不变；只有结构化返回才携带 context。
- 失败策略：候选计算或 context 校验异常继续进入现有环境获取失败路径；候选为空且配置等待时继续等待。
- baseline 影响：更新模块运行公共契约和 API baseline；无数据库、UI、迁移或发布动作。
- 风险：候选结果具有时效性，因此同一次选择不再通过第二次候选执行获取或替换 context；租约后仍复查宿主侧指纹与绑定授权。
- 未决问题：无；用户已明确实现范围与验收口径。
