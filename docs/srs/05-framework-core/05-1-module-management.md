# 5.1 模块管理系统（Module Management）

本章定义 Framework Core 中“模块管理系统”的职责边界、数据模型与功能规格。

## 5.1.1 需求说明

模块管理系统负责将 **标准模块包**（Modules 的唯一交付物，见第 7 章）接入到框架运行时，并向调度、执行与 UI 提供一致的模块视图。

模块管理系统 MUST 覆盖以下能力：

- **模块发现与登记**：从受控扫描域发现模块包，解析 manifest，构建模块注册表（Module Registry）。
- **加载与校验**：校验模块结构、命名约束、SDK 版本兼容性，并输出可诊断报告。
- **生命周期管理**：安装/卸载/升级/启用/禁用/刷新。
- **UI 扩展索引**：索引声明式 UI 与受信 micro-app 的入口与可用性状态，供 UI Host 装载与降级。
- **设置存储（settings store）**：保存模块级/工作流级的用户配置与 UI 表单数据（JSON 可序列化）。

边界约束（MUST NOT）：

- MUST NOT 执行 TaskScript/TaskFlow（执行属于 5.4）。
- MUST NOT 管理 Execution Environment 的生命周期（属于 5.2）。
- MUST NOT 允许 Modules 绕过 SDK 边界直接依赖 Core 内部实现。

## 5.1.2 需求分析分解

### 5.1.2.1 功能性需求（FR）

- **FR-CORE-MM-001 模块发现**：在一个或多个扫描域中发现候选模块包，并输出稳定的候选列表（路径 + 来源标识）。
- **FR-CORE-MM-002 manifest 解析与校验**：解析模块清单并校验必填字段、字段类型与约束（见 7.1）。
- **FR-CORE-MM-003 命名与唯一性校验**：校验 `module_name/workflow_name/task_name` 的唯一性与一致性（见 7.1）。
- **FR-CORE-MM-004 SDK 兼容性校验**：校验模块声明的 `sdk_version_range` 与当前 SDK 版本是否兼容；不兼容必须阻断加载。
- **FR-CORE-MM-005 注册表管理**：维护模块注册表，支持查询/列表/刷新，并对禁用模块在 UI 与执行侧同时生效。
- **FR-CORE-MM-006 安装/卸载/升级**：支持从本地目录或归档包安装；支持卸载与升级，并在失败时保证可回滚/不破坏已有可用状态。
- **FR-CORE-MM-007 UI 扩展索引与信任门控**：声明式 UI 可直接装载；代码型 micro-app 必须经过信任校验与能力白名单限制。
- **FR-CORE-MM-008 settings store**：提供模块级/工作流级 settings 的读写与导出能力。

### 5.1.2.2 关键用例

- UC-04 模块管理（安装/升级/卸载/刷新）
- UC-05 UI 扩展装载与降级

## 5.1.3 模块整体设计

### 5.1.3.1 结构与依赖

模块管理系统位于 Core 内部，为以下子系统提供能力：

- 5.4 自动化任务管理：获取可执行的模块/工作流索引、模块禁用状态、兼容性约束。
- 5.5 UI Host：获取模块列表、模块 UI 扩展索引、settings schema 与数据。
- 运维/诊断：获取加载报告、失败原因与修复建议。

依赖约束（MUST）：

- 模块脚本（Tasks/Workflows）只允许依赖 SDK；模块管理系统不得向模块暴露 Core 内部对象作为“后门”。

### 5.1.3.2 接口面（对 5.4/5.5/Ops）

建议对外提供的能力（语义级，非实现绑定）：

- `list_modules() / get_module(module_name)`
- `get_workflows(module_name)`
- `get_ui_extension(module_name)`
- `read_settings(scope, key) / write_settings(scope, key, value)`
- `install(source) / uninstall(module_name) / upgrade(source) / refresh()`

错误输出（MUST）：

- 必须可诊断，至少包含 `stage`（DISCOVERY / PARSE / VALIDATE / INSTALL / REGISTRY_APPLY）与 `hint`（可执行修复建议）。

### 5.1.3.3 数据与存储（含 settings store）

模块管理系统的持久化数据应至少覆盖：

- **Module Registry**：
  - 模块元信息（name/version/author/description）
  - 来源（builtin/external，路径或包来源）
  - 状态（enabled/disabled/incompatible/invalid）
  - 工作流声明与任务索引（供 UI/调度展示）
  - UI 扩展索引（declarative/micro-app/none）与可用性
- **Settings Store**：
  - 模块级：`(module_name, key) -> json`
  - 工作流级：`(module_name, workflow_name, key) -> json`

约束（MUST）：settings 的 value 必须 JSON 可序列化，以支持导出/迁移/审计。

### 5.1.3.4 错误处理与降级

- MUST：单模块加载失败不得影响其他模块可用性。
- MUST：UI 扩展加载失败必须降级到 UI Host 的“通用模块页”。
- SHOULD：对常见错误提供明确 hint（如“请对齐 module.yaml:workflows[].name 与 TaskFlow.name”）。

### 5.1.3.5 安全与隔离

- MUST：安装/解压必须防止路径穿越（zip slip）与越界写入。
- MUST：代码型 UI（micro-app）必须受信（签名/白名单/内置来源），未受信必须禁用并降级。
- SHOULD：提供可插拔的静态安全检查钩子，用于阻断明显危险的 import/调用模式（规则可随版本演进）。

## 5.1.4 功能清单（按功能级模板填写）

### 5.1.4.1 功能：模块发现

- 输入：一个或多个扫描域（内置目录/外部目录/安装缓存等）。
- 输出：候选模块包列表（路径 + 来源标识）。
- MUST：发现过程可重复且顺序稳定。
- SHOULD：忽略 `__pycache__`、临时目录等无关条目。

### 5.1.4.2 功能：加载与校验

加载与校验至少包括：

- manifest 解析（推荐 `module.yaml`；字段规范见 7.1）
- 命名与唯一性校验（module/workflow/task）
- SDK 版本兼容性校验（不兼容必须阻断加载）

输出：模块加载报告（成功/警告/失败原因与修复建议）。

### 5.1.4.3 功能：隔离与边界（含脚本安全检查）

- MUST：保证模块无法绕过 SDK 直接依赖 Core 内部实现。
- SHOULD：可配置静态安全检查，在加载阶段发现明显越界/危险行为并阻断。

### 5.1.4.4 功能：安装/卸载/刷新

- 安装（MUST）：将模块包复制/解压到受控目录并更新注册表。
- 卸载（MUST）：移除模块目录与注册表条目（settings 是否保留由策略决定）。
- 刷新（SHOULD）：重新扫描并更新注册表，输出变更摘要。

### 5.1.4.5 功能：UI 扩展索引与信任门控

- 声明式 UI：纯数据（YAML/JSON），装载不得触发任何模块代码执行。
- micro-app：可执行代码扩展，必须受信并受能力白名单控制。
- MUST：任一 UI 扩展不可用时，UI Host 必须可降级到通用模块页并展示原因摘要。
