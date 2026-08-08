# Cheese 自动化示例模块需求简报

- 项目：crawler4j
- Work item：`CR-024`
- 任务：`TASK-044`
- 状态：`requirements_ready`
- 场景：`add_requirement`
- 来源：用户要求 crawler4j 支持 Cheese 自动化模块，并在模块内提供 Cheese 自动化测试脚本
- 文档版本：`0.1.0`
- 日期：2026-07-28

## 目标

使用现有 `core-native-v2` 模块协议交付一个可校验、可打包的 Cheese 自动化示例模块；模块内携带一份可由 Cheese 执行的 Android 设置页冒烟测试脚本。

## 用户与主流程

- 用户角色：开发 crawler4j 模块、并在已授权 Android 设备上使用 Cheese 的测试人员。
- 主流程：
  1. 用户用 crawler4j SDK 校验并打包示例模块。
  2. 用户安装或解压模块，取得模块内的 Cheese JavaScript 脚本。
  3. 用户通过 Cheese 官方 VSCode/IDEA 插件在已授权 Android 设备上运行脚本。
  4. 脚本校验屏幕尺寸、打开系统设置，并确认前台包名为 `com.android.settings`。
- 异常流程：屏幕信息无效、系统设置无法打开或前台包名不匹配时，脚本抛出带步骤信息的错误。

## 需求

### `REQ-017`：提供标准 Cheese 示例模块

- 优先级：P0
- 在 `examples/cheese_automation/` 提供 `core-native-v2` 标准模块。
- 模块 workflow 返回随包携带的 Cheese 脚本路径和运行说明。
- 模块不新增 Core、Contracts、SDK 公共契约或依赖。

### `REQ-018`：提供 Cheese Android 设置页冒烟脚本

- 优先级：P0
- 脚本使用 Cheese 官方 `cheese-js` API。
- 脚本只读取屏幕宽高、打开 Android 系统设置、等待页面稳定并读取前台包名。
- 任一步骤失败必须抛出错误；成功必须输出结构化通过日志。

### `REQ-019`：校验脚本随模块发布

- 优先级：P0
- crawler4j `check full` 必须通过。
- crawler4j `package build` 和 `package verify` 必须通过。
- 安装 ZIP 必须包含 Cheese 脚本，避免打包时遗漏非 Python 资源。

## 验收标准

- `AC-024-001`：示例目录通过 `crawler4j check full`。
- `AC-024-002`：示例模块构建和校验 ZIP 成功，ZIP 内存在 `cheese_automation/cheese/settings_smoke.js`。
- `AC-024-003`：运行模块 workflow 时，结果包含存在的脚本路径和 Cheese 官方插件运行说明。
- `AC-024-004`：脚本包含 `device.getScreenWidth()`、`device.getScreenHeight()`、`app.openApp("com.android.settings")`、`app.getForegroundPkg()` 和失败断言。
- `AC-024-005`：仓库自动测试不连接真实设备，不执行 Cheese 私有协议，也不要求新增第三方依赖。

## 非功能需求

### `NFR-015`：安全与可移植性

- 仅操作 Android 系统设置，不读取账号、剪贴板、IMEI、OAID、位置或其他隐私数据。
- 不包含凭据、固定设备地址、ADB shell、root 或远端下载。
- 设备侧 E2E 由用户在已授权设备上执行；仓库测试只验证静态脚本契约和模块打包。

## 非目标

- 不逆向或实现 Cheese IDE 心跳/设备连接私有协议。
- 不让 crawler4j 直接执行 `cheese-js`。
- 不新增通用移动设备运行时、ADB 宿主工具或 Cheese 专用 Core API。
- 不连接真实设备，不执行发布、push、PR 或 merge。

## 需求分析

- `analysis_mode`：`embedded`
- `analysis_locator`：本节
- 可行性：现有模块打包器会保留非忽略的任意文件，标准模块可直接携带 `.js` 资源。
- 依赖：设备侧需要用户自行安装 Cheese 和官方 IDE 插件；crawler4j 侧无新增依赖。
- 风险：Cheese 官方未公开稳定的桌面远程执行协议，因此本工作项只交付可携带、可定位的官方 API 脚本，不伪造宿主直连能力。
- baseline 影响：无领域、总体架构、数据库、公共 API 或 UI baseline 影响。
- 领域模块映射：`MOD-003` 模块运行边界；只使用现有资源打包能力。

## 未决问题

- 用户尚未指定业务 App 与业务步骤；本版默认使用无账号、低风险的 Android 系统设置冒烟场景。需要业务 App 流程时再替换脚本步骤。

## 路由边界

- `work_item_id`：`CR-024`
- `task_card_id`：`TASK-044`
- `current_gate`：`done`
- `write_policy`：`project_fact_write`
- `allowed_paths`：
  - `.factory/workitems/CR-024/**`
  - `.factory/memory/agent-session.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/tasks.summary.md`
  - `.factory/memory/tests.summary.md`
  - `.factory/memory/review-ledger.jsonl`
  - `examples/cheese_automation/**`
  - `packages/crawler4j/tests/integration/test_sdk_cli_module_mode.py`
- `forbidden_actions`：
  - 不新增 Cheese 私有协议、逆向桥接或第三方运行时依赖
  - 不修改 crawler4j Core、Contracts 或 SDK 公共契约
  - 不连接真实设备或执行外部 Cheese 脚本
  - 不发布、推送或创建远端 PR
