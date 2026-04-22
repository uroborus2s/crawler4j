# 核心概念

开始写模块前，先把 5 个核心事实看清楚。后面所有判断，基本都围绕它们展开。

## 1. 模块是宿主里的业务交付单元

在 `crawler4j` 里，模块不是独立平台，也不是给你继续抽象框架的地方。它就是一份被宿主加载、执行、安装和升级的业务交付单元。

直接按这个边界理解：

- 宿主负责运行时、环境、任务调度、配置持久化、页面渲染、安装与升级
- 模块负责业务动作、业务流程、少量 UI 声明和交付清单

如果你在模块里开始发明第二套平台层，通常已经偏了。

## 2. 模块开发的正式落点只有几处

第一次上手时，不要被名词淹没。真正长期维护的文件和目录只有这些：

| 路径 | 解决什么问题 |
|---|---|
| `module.yaml` | 静态清单：模块名、版本、工作流、升级源、UI 入口、默认配置模板 |
| `pyproject.toml` | 模块本地开发环境和包元数据；与 `module.yaml.version` 保持一致 |
| `__init__.py` | SDK 托管薄壳，负责把模块接给 `ModuleAssembler` |
| `module_runtime.py` | 生命周期 hook、环境选择器、Hosted UI V1 声明 |
| `tasks/` | 原子业务动作 |
| `workflows/` | 业务流程编排 |
| `tests/` | 模块自己的最小回归测试 |

只要还在这条边界内写，你的模块大概率不会失控。

## 3. Hosted UI V1 是当前唯一正式 UI 契约

模块 UI 已经收口到 Hosted UI V1。正式入口只有两类：

- `core:page:<page_id>`
- `core:data_table:<view_id>`

对应的声明方式也只有两类：

- `ui.declare_page`
- `ui.declare_data_table`

这意味着：

- 模块不再导出 `PyQt6` 页面类
- 模块不再维护 `ui/` 页面目录
- `detail_menu`、`ui:*`、`micro_app` 之类旧入口都不是正式事实

如果你要做概览页、说明页、KPI 看板，选 `core:page`。
如果你要维护一批结构化快照数据，选 `core:data_table`。

## 4. CLI、宿主和 GitHub Release 各做不同的事

三者是分工关系，不是替代关系。

| 角色 | 正式职责 |
|---|---|
| CLI | 生成骨架、维护清单、跑 gate、打 ZIP、发布 Release、桥接宿主操作 |
| 宿主 | 加载模块、DevLink 联调、执行作业、渲染 Hosted UI V1、安装和升级模块 |
| GitHub Release | 正式模块 ZIP 的远端分发源 |

所以：

- 本地联调用 `host devlink`
- 正式安装用 ZIP
- 正式远端发布用 `release publish`
- 正式升级用 `host upgrade`

不要用 DevLink 代替正式交付，也不要把 wheel 当成宿主安装格式。

## 5. 配置、运行态、快照数据、历史事件是四种不同东西

这条边界如果不分清，模块很快会乱。

| 你要表达什么 | 正式入口 |
|---|---|
| 静态清单 | `module.yaml` |
| 持久配置 | `ctx.get_config()` / `ctx.config` |
| 运行态元数据 | `ctx.runtime` |
| 单次执行共享内存 | `ctx.state` |
| 当前快照数据 | `db.list_records` / `db.replace_records` |
| append-only 历史事件 | `db.append_event` / `db.query_events` |

直接记住：

- 配置不写进 `ctx.runtime`
- 运行态不写回配置
- 当前快照不塞进 `ctx.state`
- 历史事件不混进 `core:data_table`

## CLI 主线和宿主主线分别是什么

站在模块开发者角度，主线其实有两条：

### CLI 主线

```bash
module init -> task create -> workflow create -> page create / data-table create -> check full -> package build -> release publish
```

### 宿主主线

```text
DevLink 挂载 -> ATM 创建作业 -> 执行 / 调试 -> ZIP 安装 -> host upgrade
```

这两条线会在模块 ZIP 和 `upgrade_source.repo` 上汇合。

## 三条版本与升级轨道必须严格区分

这是整份指南最重要的认知之一。

### 轨道一：SDK / Core 包版本

这是平台版本，不是模块版本。

当前仓内基线：

- `crawler4j-sdk`：`0.3.0`
- `crawler4j` 宿主 / Core：`0.2.0`

它们决定的是：

- CLI 命令树长什么样
- Hosted UI V1 和 Core 能力有哪些
- 宿主能识别哪些模块契约

模块作者通常不会在一次业务模块交付里去改这两个版本。

### 轨道二：模块版本

这是你交付的模块版本，由你自己维护。

正式事实源：

- `module.yaml.version`
- 模块自己的 `pyproject.toml`

推荐只用一条命令修改：

```bash
uv run crawler4j module set version 0.1.1
```

CLI 会同步更新模块清单和模块项目包版本，避免两个版本口径漂移。

### 轨道三：宿主里的模块升级

这是“已安装模块如何拿到新 ZIP”的链路。

正式事实源：

- `module.yaml.upgrade_source.repo`
- GitHub Release 上的 ZIP 安装包

典型动作：

```bash
uv run crawler4j host upgrade check <module>
uv run crawler4j host upgrade preview <module>
uv run crawler4j host upgrade apply <module>
```

这条轨道依赖你先把新模块版本发布出去，但它本身不是在升级 SDK，也不是在升级宿主程序。

## 模块执行链可以压成一句话

你可以把当前标准模块的执行过程理解成一句话：

`module.yaml` 定义清单，`ModuleAssembler` 装配入口，`workflow` 调 `task` 做业务，`module_runtime.py` 负责 hook 和 Hosted UI V1，宿主负责执行、渲染、安装和升级。

如果你后面看见更复杂的细节，都不要离开这条主线。

## 当前明确不做什么

下面这些思路，当前都不属于正式模块开发方式：

- 自建 `ui/` 页面体系
- 自建 `config_schema.json`、`strategy.yaml` 一类第二事实源
- 在 `module.yaml` 里声明 `sdk_version_range`
- 直接连接宿主内部数据库
- 在模块里把 wheel 当成正式安装产物
- 在根 `__init__.py` 里写业务逻辑

下一步建议看 [模块结构](module-structure.md)。如果你已经知道目录长什么样，可以直接看 [构建模块](build-modules.md)。
