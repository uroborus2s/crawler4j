# 7.1 模块通用规范 (General Module Specification)

## 7.1.1 目录结构与入口

每个模块是一个独立的目录，包含清单、代码与 UI 定义。

```
modules/
  └── <module_name>/
      ├── module.yaml       # 核心清单 (Manifest)
      ├── config_schema.json # [UI] 配置 Schema (推荐)
      ├── ui.py             # [UI] 自定义 Widget 入口 (高级)
      ├── tasks/            # 任务脚本
      └── workflows/        # 工作流定义
```

本章定义“标准模块包”（Standard Module Package）的目录结构、`module.yaml`（manifest）字段约束、命名规则、UI 扩展规范与安全边界。本章是 5.1（模块管理系统）进行发现/加载/校验的依据。

## 7.1.1 需求说明

### 7.1.1.1 标准模块包交付形态

标准模块包可以是：

- 一个目录（用于开发/调试）
- 一个归档文件（用于分发/安装，例如 zip）

无论形态如何，解包后的根目录结构必须满足 7.1.3.1 的约束。

### 7.1.1.2 边界与原则

Modules MUST：

- 通过 manifest 显式声明可用的 workflows / tasks / UI 扩展
- 仅依赖 SDK（6.x），不得依赖 Core 的内部实现
- **MUST NOT** 直接依赖 `src.core` (使用 SDK 提供的 Context)。
- **MUST NOT** 包含绝对路径引用。
- 遵循命名、版本、兼容性与数据域隔离约束

Modules MUST NOT：

- 导入/调用 Core 内部包或实现细节
- 在 import 阶段执行具有副作用的逻辑（例如网络访问、写文件、启动进程）

## 7.1.2 UI 实现规范 (Module UI)

模块开发者需决定采用何种方式提供配置界面：

### 方式一：Schema (推荐)
提供 `config_schema.json`，遵循 standard JSON Schema draft-07。这将由 Core 会根据此文件自动渲染 **UI-19 全局配置页**。

**典型应用场景**:
*   **Ctrip 模块**: 定义 `account_pool` (账号列表), `sms_api_url` (验证码服务)。
*   **Waimai 模块**: 定义 `target_cities` (城市列表), `delivery_api_token` (配送接口密钥)。

**配置隔离原则**:
*   Core 为每个模块分配独立的配置存储空间 (Namespace)。
*   Ctrip 模块的代码只能读取 Ctrip 的配置，无法访问 Waimai 的配置。

```json
{
  "title": "Ctrip Global Config",
  "type": "object",
  "properties": {
    "account_pool": { 
      "type": "array", 
      "title": "公共账号池",
      "items": { "type": "string" }
    },
    "sms_api_key": { 
        "type": "string", 
        "title": "打码平台密钥", 
        "ui:widget": "password" 
    }
  }
}
```

### 方式二：Custom Widget (高级)
提供 `ui.py`，其中必须包含工厂方法：
```python
from crawler4j_sdk.ui import BaseModuleWidget

class MyWidget(BaseModuleWidget):
    def __init__(self, ctx_bridge):
        super().__init__()
        self.setup_ui()

def create_widget(ctx_bridge):
    """Entry point used by UI Host."""
    return MyWidget(ctx_bridge)
```

## 7.1.2 需求分析分解

### 7.1.2.1 功能性需求（FR）

- FR-MOD-001 目录结构约束：模块包必须包含 `module.yaml`，并按约定组织 workflows/tasks/ui。
- FR-MOD-002 manifest 可校验：manifest 必须可被 Core 校验并给出可诊断错误信息。
- FR-MOD-003 命名与唯一性：模块内 `workflow_name/task_name` 必须唯一；与模块名组合后应形成全局可唯一的三段式标识。
- FR-MOD-004 SDK 兼容性：模块必须声明 `sdk_version_range`，不兼容时 Core 必须阻断加载。
- FR-MOD-005 UI 扩展声明：模块 UI 必须通过 manifest 声明为 `none/declarative/micro_app` 之一。

### 7.1.2.2 非功能性需求（NFR）

- NFR-MOD-001 可迁移：模块包应可在不同机器/环境中安装，不依赖绝对路径。
- NFR-MOD-002 可诊断：加载失败必须能定位到文件与字段（例如 `module.yaml:workflows[0].name`）。

## 7.1.3 整体设计

### 7.1.3.1 推荐目录结构

模块根目录（Module Root）建议结构如下（示意）：

- `module.yaml`（MUST）：模块 manifest
- `workflows/`（MUST）：工作流声明文件目录
- `tasks/`（SHOULD）：任务脚本目录
- `ui/`（SHOULD）：UI 扩展目录（声明式 UI 或 micro-app）
- `assets/`（SHOULD）：静态资源（图标、说明等）

约束（MUST）：

- `module.yaml` 必须位于模块根目录
- `workflows/` 中的每个工作流文件必须可映射到一个 `TaskFlow`
- `tasks/` 中的每个任务脚本必须可映射到一个 `TaskScript`

### 7.1.3.2 module.yaml（manifest）字段规范

`module.yaml` 至少应包含以下字段（语义级约束）：

- `name`（MUST）：模块名，推荐使用小写字母/数字/下划线/短横线，且在一个 Core 实例内全局唯一
- `version`（MUST）：模块版本（SemVer）
- `description`（SHOULD）：模块描述
- `author`（SHOULD）：作者/团队信息
- `sdk_version_range`（MUST）：SDK 兼容范围字符串（例如 `>=0.5,<0.6`）
- `workflows`（MUST）：工作流清单
  - `name`（MUST）：工作流名（模块内唯一）
  - `file`（MUST）：工作流文件路径（相对 module root）
- `tasks`（SHOULD）：任务清单
  - `name`（MUST）：任务名（模块内唯一）
  - `file`（MUST）：任务脚本路径（相对 module root）
- `ui`（SHOULD）：UI 扩展声明
  - `type`（MUST）：`none | declarative | micro_app`
  - `entry`（SHOULD）：入口路径（相对 module root；type=none 时可省略）
  - `trusted`（SHOULD）：是否为受信来源（仅对 micro_app 有意义；最终由 5.1 的信任门控策略裁决）

一致性约束（MUST）：

- `workflows[].name` 必须与对应工作流文件内的 `TaskFlow.name` 一致
- `tasks[].name` 必须与对应任务脚本内的 `TaskScript.name` 一致
- 三段式全局标识：`{module_name}/{workflow_name}/{task_name}`

### 7.1.3.3 模块 UI 扩展规范

模块 UI 扩展分两类：

1. **声明式 UI（declarative）**：入口文件为 JSON/YAML 的 UI 描述；UI Host 仅渲染描述，不执行模块代码。
2. **micro-app（micro_app）**：入口为可执行前端应用；必须受信并受能力白名单限制（见 5.1、5.5）。

降级规则（MUST）：

- UI 扩展不可用时，UI Host 必须降级到通用模块页，并显示原因摘要。

### 7.1.3.4 可靠性与幂等

- 任务执行应尽量幂等：同一输入重复执行应得到等价结果或可安全重试。
- 任务结果必须通过 SDK 的 `TaskResult` 规范表达成功/失败/可重试等状态（见 6.4、6.7）。
