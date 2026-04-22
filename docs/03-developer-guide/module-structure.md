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

这就是完整的一条开发到交付链。

## 目录里每个路径负责什么

| 路径 | 正式职责 | 明确不要放什么 |
|---|---|---|
| `__init__.py` | SDK 托管薄壳、模块统一入口 | 业务逻辑、配置解析、页面逻辑 |
| `module.yaml` | 唯一静态清单 | 运行态、持久数据、宿主内部状态 |
| `module_runtime.py` | lifecycle hook、`@env_selector(...)`、Hosted UI V1 声明 | 大段业务流程、复杂领域转换 |
| `pyproject.toml` | 模块开发环境、包元数据、版本同步点 | 宿主运行时依赖安装器 |
| `tasks/` | 原子业务动作 | 多阶段流程编排 |
| `workflows/` | 业务流程编排 | 页面渲染、字段细节解析 |
| `tests/` | 模块自测 | 宿主内部实现细节 |
| `dist/` | 正式 ZIP 安装产物 | 源码事实源 |

## `module.yaml` 是唯一静态清单

它回答的不是“模块现在在跑什么”，而是“这个模块是什么”。

它至少应当描述：

- 模块身份：`name`、`display_name`、`description`
- 模块版本：`version`
- 升级来源：`upgrade_source`
- 工作流入口：`workflows`
- Hosted UI V1 页面入口：`ui_extension.pages`
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
      entry: core:page:dashboard
    - id: hotels
      label: 酒店列表
      icon: 📋
      entry: core:data_table:hotels
config_defaults:
  module:
    city: shanghai
```

这里最容易写错的只有 3 件事：

1. `upgrade_source.repo` 必须是真实的 `owner/repo`
2. `ui_extension.pages[].entry` 只允许 `core:page:<id>` 或 `core:data_table:<id>`
3. `module.yaml` 不负责声明 `sdk_version_range`

## `pyproject.toml` 是模块项目元数据，不是宿主事实源

这个文件主要服务于模块开发者自己：

- 管理本地开发依赖
- 声明模块项目包名和版本
- 支撑 `uv sync`

它和 `module.yaml` 的关系可以直接这样理解：

- `module.yaml` 是宿主识别模块的清单
- `pyproject.toml` 是你本地开发模块项目的包元数据

两者里的版本必须保持一致。推荐只用下面这条命令改版本：

```bash
uv run crawler4j module set version 0.1.1
```

CLI 会同步改这两个位置，避免版本漂移。

## `__init__.py` 保持薄壳，不要碰成业务入口

当前标准模块根入口的职责很简单：

1. 创建 `ModuleAssembler`
2. 暴露统一 `run(context)` 入口
3. 把 `module_runtime.py` 里的 hook 和 UI 声明转发给宿主

最重要的纪律只有一句：

不要在根 `__init__.py` 写业务逻辑。

安全做法：

- 只改 `module.yaml`
- 只改 `module_runtime.py`
- 只改 `tasks/` 和 `workflows/`

危险做法：

- 删除 SDK 托管的转发逻辑
- 手写第二套装配入口
- 把 UI handler 或业务流程塞进根入口

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
- 数据表 handler

这里的关键词是“薄”。如果你在这里写大段业务流程、复杂循环或 service 层，模块结构就已经跑偏了。

## `tasks/` 和 `workflows/` 的分工不要反

### `tasks/`

放原子业务动作，例如：

- 登录
- 抓一页列表
- 打开详情页
- 提交表单

### `workflows/`

放流程编排，例如：

- 先登录，再抓列表，再抓详情
- 分支选择
- 循环翻页
- stop 判断

只要你觉得“这里已经出现第二阶段”，大概率就该从 task 提升到 workflow。

## Hosted UI V1 相关文件实际落在哪里

当前 UI 不再新建 `ui/` 目录。页面和数据表都落在两个地方：

| 位置 | 作用 |
|---|---|
| `module.yaml.ui_extension.pages` | 定义宿主里会出现哪些页面入口 |
| `module_runtime.py` | 定义这些入口背后的 `declare_ui()`、页面 schema、load handler、数据表 handler |

所以：

- `page create` 会同时改 `module.yaml` 和 `module_runtime.py`
- `data-table create` 也会同时改这两个文件

如果你看见有人手写 `ui/SomePage.py`，那已经不是当前正式结构了。

当前 `crawler4j check structure / release / full` 与 `package build` 都会把顶层 `ui/` 目录当成旧结构残留直接阻断；不要再把它当成“还能顺手兼容”的可选目录。

## 交付物最终长什么样

模块交付给宿主时，正式产物是 ZIP，不是源码目录，也不是 wheel。

典型交付物：

```text
dist/hotel_demo-0.1.0.zip
```

这个 ZIP 后续会进入两条链路：

1. 宿主本地安装：`host install`
2. GitHub Release 分发后，宿主执行 `host upgrade`

也就是说，模块目录本身是开发事实源，ZIP 才是正式安装事实源。

## 当前明确不要新增的东西

下面这些文件或目录，当前都不属于标准模块结构：

- `ui/`
- `config_schema.json`
- `strategy.yaml`
- `sdk_version_range`
- 宿主私有数据库接入代码
- 第二套 `services/`、`repositories/`、`managers/`

如果你在一个新模块里看到这些内容，优先判断它是不是旧结构残留，而不是把它继续扩散。

下一步建议看 [构建模块](build-modules.md)。
