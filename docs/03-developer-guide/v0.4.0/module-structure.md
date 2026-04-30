# 模块结构

> 版本绑定：本文是 0.4.0 专属结构。0.4.x SDK 初始化出的模块必须是 `core-native-v2` 结构，不生成也不维护 0.3.x 的固定导出开发模式。

0.4.0 模块结构围绕装饰器扫描组织。目录名可以按团队习惯调整，但推荐使用下面的标准布局。

```text
hotel_demo/
├── __init__.py
├── module.yaml
├── pyproject.toml
├── .crawler4j/
│   └── manifest.lock.json
├── interfaces/
│   └── *.py
├── objects/
│   └── *.py
├── workflows/
│   └── *.py
├── tasks/
│   └── *.py
├── data/
│   └── *.py
└── pages/
    ├── *.py
    └── <group>/
        └── *.py
```

## 每个位置负责什么

| 路径 | 职责 |
|---|---|
| `module.yaml` | 模块元信息、`runtime_api`、升级源、页面菜单、资源池、配置默认值等宿主静态配置 |
| `.crawler4j/manifest.lock.json` | SDK 扫描装饰器生成的只读快照 |
| `interfaces/*.py` | `@interface` 能力类型 |
| `objects/*.py` | `@component` 业务对象和编排对象 |
| `workflows/*.py` | `@workflow` workflow 类 |
| `tasks/*.py` | `@page_action` 页面操作纯函数 |
| `data/*.py` | `@data_table`、`@data_query` 数据契约 |
| `pages/*.py` / `pages/<group>/*.py` | Hosted UI 页面 schema 与 handler |

`tasks/` 在 v2 中承载 page action。保留这个目录名是为了迁移和工程习惯，但它不再表示 v1 `TaskSpec` 任务，也不再承载 `TASK/execute` 主路径。

0.4.x SDK 不生成 `hooks/`、`env_selectors/`、`data/sql` 或 `data/seeds` 作为运行能力事实源。当前分支只支持 0.4.0 的 `core-native-v2` 主路径，旧目录需要在 0.3.x 分支维护。

## `module.yaml` 最小示例

```yaml
runtime_api: core-native-v2
name: hotel_demo
display_name: 酒店示例
version: 0.1.0
upgrade_source:
  repo: your-org/hotel_demo
ui_extension:
  pages:
    - id: dashboard
      label: Dashboard
      icon: chart
```

运行能力不要写进 `module.yaml`。它们来自装饰器扫描和 manifest lock。

## 根包要求

`__init__.py` 只是普通 Python 包入口。Core 不从这里读取运行入口，也不要求根包提供 `run()` 或装配器。

## manifest lock

lock 文件通过命令生成：

```bash
uv run crawler4j manifest lock
```

lock 内容来自装饰器扫描，通常包含：

- interfaces
- components
- workflows
- page actions
- data tables
- data queries
- 注入关系
- 对象参数 schema
- 诊断摘要

不要手写 lock。打包前如果源码装饰器和 lock 不一致，SDK 应阻断。

最小结构示例：

```json
{
  "lock_version": 1,
  "runtime_api": "core-native-v2",
  "module": "hotel_demo",
  "source_hash": "sha256:...",
  "generated_at": "2026-04-30T00:00:00Z",
  "interfaces": [{"name": "labor", "source": "interfaces/labor.py"}],
  "components": [
    {
      "name": "api_labor",
      "implements": "labor",
      "source": "objects/api_labor.py",
      "parameters": [{"name": "base_url", "type": "string"}],
      "inject": []
    }
  ],
  "workflows": [{"name": "hotel_sync", "source": "workflows/hotel_sync.py"}],
  "page_actions": [{"name": "open_home_page", "source": "tasks/open_home_page.py"}],
  "data_tables": [{"name": "hotels", "source": "data/hotels.py"}],
  "data_queries": [{"name": "ready_hotels", "source": "data/hotels.py"}],
  "diagnostics": []
}
```

规则：

- 开发期以代码装饰器为事实源。
- `manifest lock` 是 SDK 生成的扫描快照。
- DevLink 目标行为是重新扫描源码并报告诊断。
- ZIP 安装目标行为是先读 lock，再按需重扫源码确认 lock 未过期。

迁移旧模块时，按 [从 v0.3.0 迁移](./migration-from-v0.3.0.md) 处理旧结构。新模块直接从本页结构开始。
