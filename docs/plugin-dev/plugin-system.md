# 插件系统设计 (Plugin System Design)

Crawler4j 的插件系统是其扩展能力的基石。MMS (Module Management System) 负责插件的发现、加载、校验和生命周期管理。

## 📦 模块清单 (Module Manifest)

每个模块必须在根目录下包含一个清单文件（通常为 `module.yaml` 或直接在代码中定义元数据），用于描述模块的属性、依赖和功能。

### 数据结构 (`ModuleManifest`)

根据 SDK 定义，模块清单包含以下核心字段：

| 字段 | 类型 | 必须 | 说明 |
| :--- | :--- | :--- | :--- |
| `name` | String | ✅ | 模块唯一标识符 (如 `ctrip-flight`)。只能包含字母、数字、下划线、连字符。 |
| `version` | String | ✅ | 语义化版本号 (如 `1.0.0`)。 |
| `display_name` | String | ❌ | UI 显示名称 (如 "携程机票抓取")。 |
| `description` | String | ❌ | 模块功能描述。 |
| `sdk_version_range` | String | ❌ | 兼容的 SDK 版本范围 (如 `>=1.0.0`)。 |
| `workflows` | List | ❌ | 模块包含的工作流列表。 |
| `ui_extension` | Object | ❌ | UI 扩展配置（见下文）。 |

### 工作流定义 (`WorkflowInfo`)

模块的核心功能通过工作流暴露。一个模块可以包含多个工作流：

```yaml
workflows:
  - name: "search_flight"
    display_name: "机票查询"
    entry_class: "tasks.SearchTask"  # 对应的 TaskScript 类
    tasks: ["tasks/step1.py", "tasks/step2.py"] # 涉及的文件（供打包引索）
```

### UI 扩展 (`UIExtensionInfo`)

模块可以扩展主程序的 UI，例如添加自定义配置页面或详情页菜单。

```yaml
ui_extension:
  type: "declarative"  # 或 "micro_app"
  entry: "ui/config_page.yaml"
  nav_item:
    icon: "✈️"
    label: "机票业务"
    path: "ctrip"
```

## 🔄 加载机制

MMS 支持从以下来源加载模块：

1.  **Builtin (内置)**: 位于 `modules/` 目录下的核心模块。
2.  **External (外部)**: 用户安装到特定目录的第三方模块。

系统启动时，MMS 会扫描这些目录，解析清单文件，并验证依赖关系。只有状态为 `enabled` 且版本兼容的模块才会被最终加载。
