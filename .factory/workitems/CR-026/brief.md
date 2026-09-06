# CR-026 HubStudio 指纹浏览器支持

- 状态：`approved_for_implementation`
- 场景：`add_requirement`
- 需求来源：用户确认的 HubStudio Local API 支持需求
- 官方文档：`https://api-docs.hubstudio.cn/8331450m0`
- 分析模式：`embedded`
- 分析定位：本文“需求分析”章节

## 目标

在不改动现有环境公共接口、数据库 schema 和环境列表列结构的前提下，新增 `hubstudio` 指纹浏览器 Provider，使其具备与 VirtualBrowser 一致的 REM 管理和用户操作能力。

## 需求

- `CR-026-REQ-001`：注册独立 `hubstudio` Provider，不继承、分支或改写 `virtualbrowser` Provider 行为。
- `CR-026-REQ-002`：支持创建、打开、CDP 连接、断开、关闭、运行状态、健康检查、删除和已有环境导入。
- `CR-026-REQ-003`：支持名称更新、代理更新、指纹刷新、Cookie 全量读写和单环境缓存清理。
- `CR-026-REQ-004`：`containerCode` 作为稳定环境 ID 存入 `Environment.external_id` 并放入 `BrowserHandle.browser_id`；`browserID` 仅作为 HubStudio 缓存 API 的运行时 ID，由 Provider 独立缓存，不污染通用环境 ID。
- `CR-026-REQ-005`：REM 创建、编辑、启停、销毁、导入、代理同步和缓存清理入口增加 HubStudio；ATM 指纹浏览器供应商列表可选 `hubstudio`。
- `CR-026-REQ-006`：不新增 `EnvType`，`hubstudio` 沿用 `EnvType.VIRTUAL_BROWSER` 作为“指纹浏览器”兼容分类，运行时以 `provider="hubstudio"` 路由。
- `CR-026-REQ-007`：已有 Provider 的环境记录、列表列、创建默认值和行为保持不变。
- `CR-026-NFR-001`：不记录 Authorization、代理密码或 Cookie 内容；HTTP 必须 `trust_env=False` 且校验 HTTP 与业务状态码。

## 验收标准

1. `list_providers()` 包含 `hubstudio`，原有 Provider 仍在且默认选择不变。
2. HubStudio 所有生命周期和管理 API 通过伪服务契约测试，CDP 使用 `http://127.0.0.1:{debuggingPort}`。
3. 单次启动后同时保存 `containerCode` 和 `browserID`；缓存清理仅向 `browserOauths` 传 `browserID`。
4. 进程重启后缓存中无 `browserID` 时，Provider 通过一次临时打开/关闭重建运行时 ID，不写数据库。
5. HubStudio 已有环境导入后 `external_id == containerCode`，任务配置 `provider == "hubstudio"` 且 `env_type == VIRTUAL_BROWSER`。
6. UI 不新增环境列；HubStudio 可被选择、显示、编辑和清理缓存。
7. HubStudio 刷新指纹提示明确标注：厂商 API 不支持完整指纹回读和 location 原地修复；UI 不显示 HubStudio location 修复操作。
8. HubStudio 定向测试、相邻 REM/ATM/UI 回归和 Ruff 全部通过。

## 需求分析

- 领域：REM Provider 是能力 owner；System 管理外部应用启动与配置；ATM 仅添加 Provider 选项和兼容类型映射。
- baseline 影响：无数据库、公共环境接口或跨服务契约变更；仅增加一个内置 Provider 实现和用户界面选项。
- 风险：中风险。主要风险是厂商返回结构差异、`containerCode/browserID` 混用以及回归影响旧 Provider。
- 厂商限制：HubStudio API 未提供完整指纹回读契约和 location 专用原地修复契约；本次不伪造这两项能力。

## 非目标

- 不修改数据库 schema。
- 不增加 `HUBSTUDIO_BROWSER` 或重命名现有 `EnvType`。
- 不抽取或搬迁 BitBrowser/VirtualBrowser 旧实现。
- 不实现厂商未提供的完整指纹回读或 location 修复。
- 不连接真实 HubStudio 帐号或执行破坏性外部操作。
