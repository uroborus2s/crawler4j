# 模块结构

把模块目录看成一份正式交付物，会更容易理解所有约束。

模块不是“源码目录 + 一堆临时脚本”，而是一份最终会被宿主打包、安装、升级的产品单元。

## 标准目录长什么样

当前 `crawler4j module init` 生成的标准模块目录如下：

```text
hotel_demo/
├── __init__.py
├── .gitignore
├── .python-version
├── README.md
├── module.yaml
├── module_runtime.py
├── pyproject.toml
├── tasks/
├── tests/
└── workflows/
```

后续真正交付时，还会多一个：

```text
dist/
└── hotel_demo-0.1.0.zip
```

## 目录里每个路径负责什么

| 路径 | 正式职责 | 明确不要放什么 |
|---|---|---|
| `__init__.py` | SDK 托管薄壳、模块统一入口 | 业务逻辑、页面渲染、配置解析 |
| `module.yaml` | 唯一静态清单 | 运行态、持久数据、宿主内部状态 |
| `module_runtime.py` | lifecycle hook、`@env_selector(...)`、Hosted UI 页面声明 | 大段业务流程、复杂领域转换 |
| `pyproject.toml` | 模块开发环境、包元数据、版本同步点 | 宿主运行时依赖安装器 |
| `tasks/` | 原子业务动作 | 多阶段流程编排 |
| `workflows/` | 业务流程编排 | 页面渲染、字段细节解析 |
| `tests/` | 模块自测 | 宿主内部实现细节 |
| `dist/` | 正式 ZIP 安装产物 | 源码事实源 |

## `module.yaml` 是唯一静态清单

它至少应当描述：

- 模块身份：`name`、`display_name`、`description`
- 模块版本：`version`
- 升级来源：`upgrade_source`
- 工作流入口：`workflows`
- 页面导航：`ui_extension.pages`
- 默认配置模板：`config_defaults`

最小示例：

```yaml
name: hotel_demo
version: 0.1.0
display_name: 酒店采集示例
description: 抓取并维护酒店快照数据
author: crawler4j
upgrade_source:
  type: github_release
  repo: your-org/hotel_demo
  allow_prerelease: false
workflows:
  - name: hotel_sync
    display_name: 酒店同步
    description: 抓取并刷新酒店列表
ui_extension:
  pages:
    - id: dashboard
      label: 运营看板
      icon: 📄
    - id: accounts
      label: 账号列表
      icon: 📄
config_defaults:
  module:
    city: shanghai
```

这里最容易写错的只有 3 件事：

1. `upgrade_source.repo` 必须是真实的 `owner/repo`
2. `ui_extension.pages[]` 只允许 `id`、`label`、`icon`
3. `module.yaml` 不负责声明 `sdk_version_range`

## `module_runtime.py` 是模块和宿主的接缝层

它只应该承担“很薄”的宿主接缝职责：

- `prepare_env`
- `init_env`
- `before_run`
- `on_success`
- `on_failure`
- `on_timeout`
- `on_cleanup`
- `@env_selector(...)`
- `declare_ui()`
- `build_*_page_schema()`
- `load_*_page()`
- 内联表格 `query_handler()`

这里的关键词是“薄”。如果你在这里写大段业务流程、复杂循环或 service 层，模块结构就已经跑偏了。

## Hosted UI 相关文件实际落在哪里

当前 UI 不再新建 `ui/` 目录。页面都落在两个地方：

| 位置 | 作用 |
|---|---|
| `module.yaml.ui_extension.pages` | 定义宿主里会出现哪些页面入口 |
| `module_runtime.py` | 定义这些入口背后的 `declare_ui()`、页面 schema、`load_handler()` 与内联表格查询函数 |

所以：

- `page create` 会同时改 `module.yaml` 和 `module_runtime.py`
- 需要多个页面时，就执行多次 `page create`
- 可编辑表格和只读表格都在页面 schema 里通过 `DataTable` 表达

如果你看见有人手写 `ui/SomePage.py`，那已经不是当前正式结构了。

当前 `crawler4j check structure / release / full` 与 `package build` 都会把顶层 `ui/` 目录当成旧结构残留直接阻断；不要再把它当成“还能顺手兼容”的可选目录。
