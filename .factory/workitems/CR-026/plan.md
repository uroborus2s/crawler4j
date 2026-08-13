# HubStudio 指纹浏览器支持实施与重构计划

> **给执行者：** 依赖顺序为 TASK-046/TASK-047 同层并行，然后 TASK-048 集中质量门。

**目标：** 新增独立 `hubstudio` Provider，覆盖 VirtualBrowser 已有的 REM 管理与用户操作，不改通用环境契约和数据库。

**架构：** HubStudio HTTP 协议适配与 Provider 单独放入 `hubstudio_provider.py`，复用现有 `BaseProvider` 和 `BrowserHandle.safe_connect()`。`provider.py` 仅负责注册，REM/System/ATM/UI 仅增加映射与能力可见性，不修改旧 Provider 内部。

**技术栈：** Python 3.12、asyncio、httpx、Playwright CDP、PyQt6、pytest、ruff、uv。

**工作项：** `CR-026`

**状态：** `completed`

---

## 输入

- 已批准需求：`.factory/workitems/CR-026/brief.md`
- 官方 API：`https://api-docs.hubstudio.cn/8331450m0`
- 已回源代码：REM Provider/Manager/Handle/Model、ATM RunProfile/UI、System Config/ExternalApp 与相关定向测试。

## 范围与重构边界

### 必须实现

- HubStudio Client：统一 POST、响应校验、认证头、超时和敏感数据隔离。
- HubStudio Provider：生命周期、Cookie、缓存、更新、已有环境导入和 CDP。
- 宿主集成：注册、配置、外部应用就绪、REM/ATM/UI 映射。
- 厂商限制可见：完整指纹回读与 location 修复不对 HubStudio 暴露。

### 刻意不重构

- 不把现有 3000+ 行 `provider.py` 全量拆分；这会扩大回归面，且不是 HubStudio 的必要条件。
- 不新增 Provider 工厂、能力层级或通用运行时 ID 表；现有注册表和 Provider 内存状态已足够。
- 不重命名 `EnvType.VIRTUAL_BROWSER`；保留旧 RunProfile 兼容，用 `provider` 实现厂商路由。

## 文件

| 类型 | 路径 | 职责 |
|---|---|---|
| 新建 | `packages/crawler4j/src/core/rem/hubstudio_provider.py` | HubStudio API 协议和 Provider 实现 |
| 修改 | `packages/crawler4j/src/core/rem/provider.py` | 注册 HubStudio Provider |
| 修改 | `packages/crawler4j/src/core/rem/__init__.py` | 延迟导出 HubStudio Provider |
| 修改 | `packages/crawler4j/src/core/rem/manager.py` | 指纹 Provider 集合与外部应用路由 |
| 修改 | `packages/crawler4j/src/core/rem/import_job_service.py` | HubStudio 导入环境映射为指纹浏览器类别 |
| 修改 | `packages/crawler4j/src/core/rem/ui/env_list_widget.py` | 创建、显示和操作 Provider 选项，不改列 schema |
| 修改 | `packages/crawler4j/src/core/rem/ui/edit_env_dialog.py` | HubStudio 缓存清理与厂商限制提示 |
| 修改 | `packages/crawler4j/src/core/atm/ui/run_profile_dialog.py` | Provider 选项及 `VIRTUAL_BROWSER` 兼容映射 |
| 修改 | `packages/crawler4j/src/core/system/config_center.py` | HubStudio 端口/API Key/程序路径配置 |
| 修改 | `packages/crawler4j/src/core/system/external_app_service.py` | HubStudio 检测、启动和真实 API 就绪检查 |
| 测试 | `packages/crawler4j/tests/unit/test_core/test_rem/test_hubstudio_provider.py` | API 契约、ID 隔离和 Provider 行为 |
| 测试 | `packages/crawler4j/tests/unit/test_core/test_rem/test_provider.py` | Provider 注册 |
| 测试 | `packages/crawler4j/tests/unit/test_core/test_rem/test_import_job_service.py` | HubStudio EnvType/Provider 映射 |
| 测试 | `packages/crawler4j/tests/unit/test_core/test_rem/test_env_list_widget.py` | 列表列不变与 HubStudio 选项/动作 |
| 测试 | `packages/crawler4j/tests/unit/test_core/test_rem/test_edit_env_dialog.py` | 缓存按钮和厂商限制文案 |
| 测试 | `packages/crawler4j/tests/unit/test_core/test_atm/test_run_profile_dialog.py` | ATM Provider 映射与旧默认值回归 |
| 测试 | `packages/crawler4j/tests/unit/test_core/test_system/test_config_center.py` | HubStudio 配置默认值 |
| 测试 | `packages/crawler4j/tests/unit/test_core/test_system/test_external_app_service.py` | HubStudio API 就绪检查 |

## 共享契约

- Provider 名：`hubstudio`；显示名：`HubStudio`。
- 稳定 ID：`str(containerCode)`；运行时 ID：`str(browserID)`。
- `BrowserHandle.browser_id` 继续表示稳定 Provider 环境 ID；`BrowserHandle.ws_url` 表示 `http://127.0.0.1:{debuggingPort}`。
- `HubStudioProvider._runtime_browser_ids` 以 `containerCode -> browserID` 保存；不持久化。
- 创建默认：`asDynamicType=0`、`proxyTypeName="不使用代理"`、`labels=[]`；代理与 `advancedBo` 按已提供参数增量下发。
- 业务成功：HTTP 成功且顶层 `code == 0`；包含 `statusCode` 的操作还需 `statusCode == "0"`。
- 指纹检查方法保持 BaseProvider 空结果；不生成虚假验证通过证据。

## 任务

### TASK-046：HubStudio API 适配与 Provider

**最小任务切片：**

- 目标：交付可独立测试的 HubStudio Client/Provider，覆盖 `CR-026-REQ-002..004` 和 `CR-026-NFR-001`。
- 依赖：`BaseProvider`、`BrowserHandle`、`Environment`、`ProxyConfig`。
- 实现：一个新模块；无公共接口和 schema 变更。
- 风险：`medium`。

**允许修改：**

- `packages/crawler4j/src/core/rem/hubstudio_provider.py`
- `packages/crawler4j/tests/unit/test_core/test_rem/test_hubstudio_provider.py`

- [x] RED：先写请求路径/载荷、错误校验、创建、生命周期、Cookie、导入和 ID 分离失败测试。
- [x] GREEN：实现最小 Client/Provider。
- [x] 运行：

```bash
uv run pytest packages/crawler4j/tests/unit/test_core/test_rem/test_hubstudio_provider.py -q
uv run ruff check packages/crawler4j/src/core/rem/hubstudio_provider.py packages/crawler4j/tests/unit/test_core/test_rem/test_hubstudio_provider.py
```

期望：测试和 Ruff 全通过。

### TASK-047：宿主注册、配置与 UI/ATM 集成

**最小任务切片：**

- 目标：交付 `CR-026-REQ-001/005..007`，保证旧 Provider 列、默认值和列表 schema 不变。
- 依赖：共享契约已锁定，可与 TASK-046 并行。
- 风险：`medium`。

**允许修改：** 本计划文件表中除 `hubstudio_provider.py` 和 `test_hubstudio_provider.py` 外的所有源码/测试路径。

- [x] RED：新增 HubStudio 注册、配置、就绪检查、导入映射、UI 选项/能力与旧默认值测试。
- [x] GREEN：只增加必要常量、枚举项、配置项和分支。
- [x] 运行：

```bash
uv run pytest packages/crawler4j/tests/unit/test_core/test_rem/test_provider.py packages/crawler4j/tests/unit/test_core/test_rem/test_import_job_service.py packages/crawler4j/tests/unit/test_core/test_rem/test_env_list_widget.py packages/crawler4j/tests/unit/test_core/test_rem/test_edit_env_dialog.py packages/crawler4j/tests/unit/test_core/test_atm/test_run_profile_dialog.py packages/crawler4j/tests/unit/test_core/test_system/test_config_center.py packages/crawler4j/tests/unit/test_core/test_system/test_external_app_service.py -q
uv run ruff check packages/crawler4j/src/core/rem/provider.py packages/crawler4j/src/core/rem/manager.py packages/crawler4j/src/core/rem/import_job_service.py packages/crawler4j/src/core/rem/ui/env_list_widget.py packages/crawler4j/src/core/rem/ui/edit_env_dialog.py packages/crawler4j/src/core/atm/ui/run_profile_dialog.py packages/crawler4j/src/core/system/config_center.py packages/crawler4j/src/core/system/external_app_service.py
```

期望：新增映射与旧行为回归全通过。

### TASK-048：集中质量门

- [x] 汇总 TASK-046/047 diff，检查公共契约/schema/旧列无变更。
- [x] 运行 HubStudio 契约、REM/ATM/System/UI 相邻回归。
- [x] 运行 `uv run ruff check` 覆盖变更文件和 `git diff --check`。
- [x] 生成一套 evidence/report/review-input，然后交给独立 Terra reviewer 只读审核。
- [x] 审核问题已回流原实现者整改，并完成复测与独立复审。

## 测试策略

- RED/GREEN：开发者在各自切片内完成。
- API 契约：全部使用 mock HTTP client，覆盖端点、载荷、数据形状和错误；不连真实账号。
- 运行时 ID：显式断言 `containerCode != browserID`，并断言缓存清理仅使用后者。
- 回归：覆盖 Provider registry、REM import/manager、ATM dialog、REM dialogs/list、ConfigCenter/ExternalApp。
- 限制：断言 HubStudio 不出现 location repair action，提示含“厂商限制”。
- 未运行：真实 HubStudio E2E；原因是当前未提供本地客户端、API Key 和可销毁测试环境。

## 集中质量门

- 计划自审：`passed`
- 批次代码评审：`approved`（Critical `0` / Important `0`）
- 批次验证：`passed`（`167 passed`，Ruff、diff-check、双导入探针通过）
- 提交：`completed`（本次提交）
- 记忆同步：`passed`

## 计划自审

- 规格覆盖：`CR-026-REQ-001..007` 和 `CR-026-NFR-001` 均映射到 TASK-046/047 与 TASK-048。
- 占位符扫描：所有实施步骤均包含精确文件、行为和验证命令。
- 类型一致：`containerCode` 和 `browserID` 全程转为字符串；`debuggingPort` 转为 HTTP CDP URL。
- 可构建性：只使用已有 httpx/Playwright/pytest/PyQt6，不增加依赖。
- 质量收敛：单一批次集中测试和独立评审，不为每个小改动生成评审物。
