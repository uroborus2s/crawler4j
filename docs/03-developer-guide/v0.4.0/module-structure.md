# 模块结构

> 版本绑定：本文是 0.4.0 专属结构。0.4.x SDK 初始化出的模块必须是 `core-native-v2` 结构，不生成也不维护 0.3.x 的固定导出开发模式。

0.4.0 模块结构围绕装饰器扫描组织。标准模块根目录用固定文件和固定目录承载不同能力入口；开发者可以在这些目录下继续按业务拆文件，但不要为同类能力另建第二套事实源。

```text
hotel_demo/
├── .gitignore
├── .python-version
├── __init__.py
├── README.md
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
├── candidates/
│   └── *.py
├── cleanups/
│   └── *.py
└── pages/
    ├── *.py
    └── <group>/
        └── *.py
```

## 根目录固定文件

| 路径 | 职责 | 维护规则 |
|---|---|---|
| `__init__.py` | Python 包入口，让模块根目录可被 SDK 和 Core 作为包导入 | 只保留包入口语义，不写 `run()`、对象装配器或运行时薄壳 |
| `module.yaml` | 模块静态清单，声明 `name`、`display_name`、`version`、`runtime_api`、`upgrade_source`、`config_defaults.module` 等宿主静态配置 | `runtime_api` 必须是 `core-native-v2`；不要写 workflows、objects、interfaces、tasks、data、ui_extension 或 resource_pools |
| `pyproject.toml` | 模块开发环境和依赖声明 | 运行时代码只依赖 `crawler4j-contracts`；`crawler4j-sdk` 只作为开发依赖和 CLI 工具 |
| `README.md` | 模块开发、调试、交付说明 | 面向模块维护者说明业务入口、配置和验收命令，不作为 Core 运行事实源 |
| `.python-version` | 本地开发 Python 版本提示 | 与当前 SDK 支持的 Python 版本保持一致 |
| `.gitignore` | 忽略本地缓存、构建产物和虚拟环境 | 不要忽略 `module.yaml`、源码目录或 `.crawler4j/manifest.lock.json` |

## 固定文件夹和含义

| 文件夹 | 扫描入口 | 含义与边界 |
|---|---|---|
| `.crawler4j/` | `.crawler4j/manifest.lock.json` | SDK 工作目录。`manifest.lock.json` 是 `crawler4j manifest lock` 扫描装饰器后生成的发布快照，打包、ZIP 安装和外部校验都会使用它；开发者不要手写这个文件，源码变更后重新生成。 |
| `interfaces/` | `@interface` | 能力接口目录。这里声明“模块需要什么能力类型”，例如账号服务、酒店检索服务或订单提交能力。接口只表达协议和类型边界，不放具体业务流程、浏览器动作或数据库写入。 |
| `objects/` | `@component` | 组件对象目录。这里放接口实现、业务客户端、编排器、适配器等可被对象图装配的对象。组件可以声明 `implements`、`inject` 和 `object_param(...)`，也可以按需实现 `setup(ctx, workflow)` / `cleanup(ctx, outcome)`。Core 会为每个 task/env 创建独立对象图。 |
| `workflows/` | `@workflow` | 工作流目录。这里放一次任务运行的主编排类，构造函数只接收注入对象，不接收普通运行参数；业务流程通过 `run(ctx)` 执行并返回 `TaskResult`。一个模块可以有多个 workflow，运行模板选择其中一个。 |
| `tasks/` | `@page_action` | 页面操作目录。v2 里的 `tasks/` 只承载 Hosted UI 或工作流可复用的页面动作纯函数，例如打开页面、点击按钮、读取 DOM 或触发一次业务动作。它不再表示 v1 `TaskSpec` 任务，也不再承载 `TASK/execute` 主路径。 |
| `data/` | `@data_table`、`@data_query` | 数据契约目录。这里声明模块实体表、托管快照表和命名查询。`@data_table` 默认是 `custom_table`，旧快照语义必须显式写 `storage_mode="managed_dataset"`；运行时代码通过 `ctx.db` 读写，不能把数据契约再写回 `module.yaml.data`、`data/sql` 或 `data/seeds`。 |
| `pages/` | `@page` | Hosted UI 页面目录。这里声明仪表盘、列表页、详情页等宿主页 schema、菜单状态和 handler。可平铺为 `pages/*.py`，也可用一层业务分组 `pages/<group>/*.py`；是否出现在左侧菜单只由 `@page(menu=True)` 决定。 |
| `candidates/` | `@env_candidates` | 环境候选目录。这里放同步纯函数，返回可用于运行的 env id 列表或 `EnvCandidates` 链式查询。Core 每次调度实时求值，模块不维护资源池同步快照，也不直接处置环境生命周期。 |
| `cleanups/` | `@env_cleanup_candidates` | 环境清理候选目录。这里放同步纯函数，只表达“模块认为已绑定且业务上可丢弃”的环境候选。真正删除由宿主环境管理页预览、确认和二次安全校验后执行，模块函数不直接删除环境。 |

这些固定目录是 SDK 扫描、manifest lock、DevLink、打包和宿主安装共同依赖的入口。目录内部可以按业务拆成多个 `.py` 文件；除 `pages/<group>/*.py` 支持一层页面分组外，其他能力建议保持直接、可扫读的文件组织。

0.4.x SDK 不生成 `hooks/`、`env_selectors/`、`data/sql` 或 `data/seeds` 作为运行能力事实源。当前分支只支持 0.4.0 的 `core-native-v2` 主路径，旧目录需要在 0.3.x 分支维护。

环境选择统一写在 `candidates/` 下。模块开发者只实现 `@env_candidates` 同步纯函数，函数可以直接返回 env id 列表，也可以返回 `EnvCandidates` 链式查询。Core 每次调度都会实时求值，不要求模块同步或物化资源池。

批量环境清理统一写在 `cleanups/` 下。模块开发者只实现 `@env_cleanup_candidates` 同步纯函数，函数同样可以返回 env id 列表或 `EnvCandidates` 链式查询。宿主环境管理页点击 `清理环境` 后会统一收集孤岛环境、模块未认领环境、owner 模块缺失环境和模块清理候选，生成预览清单、提示确认，并只删除当前仍满足安全条件的环境。

## `module.yaml` 最小示例

```yaml
runtime_api: core-native-v2
name: hotel_demo
display_name: 酒店示例
version: 0.1.0
upgrade_source:
  type: github_release
  repo: your-org/hotel_demo
  allow_prerelease: false
config_defaults:
  module: {}
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
- pages
- data tables
- data queries
- env candidates
- env cleanup candidates
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
  "pages": [{"name": "dashboard", "source": "pages/dashboard.py", "menu": true}],
  "data_tables": [{"name": "hotels", "source": "data/hotels.py"}],
  "data_queries": [{"name": "ready_hotels", "source": "data/hotels.py"}],
  "env_candidates": [{"name": "ready_accounts", "source": "candidates/ready_accounts.py"}],
  "env_cleanup_candidates": [{"name": "unused_accounts", "source": "cleanups/unused_accounts.py"}],
  "diagnostics": []
}
```

规则：

- 开发期以代码装饰器为事实源。
- `manifest lock` 是 SDK 生成的扫描快照。
- DevLink 目标行为是重新扫描源码并报告诊断。
- ZIP 安装目标行为是先读 lock，再按需重扫源码确认 lock 未过期。

迁移旧模块时，按 [从 v0.3.0 迁移](./migration-from-v0.3.0.md) 处理旧结构。新模块直接从本页结构开始。
