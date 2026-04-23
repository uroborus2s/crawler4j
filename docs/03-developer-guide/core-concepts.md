# 核心概念

开始写模块前，先把 5 个核心事实看清楚。后面所有判断，基本都围绕它们展开。

## 1. 模块是宿主里的业务交付单元

在 `crawler4j` 里，模块不是独立平台，也不是给你继续抽象框架的地方。它就是一份被宿主加载、执行、安装和升级的业务交付单元。

直接按这个边界理解：

- 宿主负责运行时、环境、任务调度、配置持久化、页面渲染、安装与升级
- 模块负责业务动作、业务流程、页面声明和页面数据

如果你在模块里开始发明第二套平台层，通常已经偏了。

## 2. 模块开发的正式落点只有几处

真正长期维护的文件和目录只有这些：

| 路径 | 解决什么问题 |
|---|---|
| `module.yaml` | 静态清单：模块名、版本、工作流、升级源、页面导航、默认配置模板 |
| `pyproject.toml` | 模块本地开发环境和包元数据；与 `module.yaml.version` 保持一致 |
| `__init__.py` | SDK 托管薄壳，负责把模块接给 `ModuleAssembler` |
| `module_runtime.py` | 生命周期 hook、环境选择器、Hosted UI 页面声明 |
| `tasks/` | 原子业务动作 |
| `workflows/` | 业务流程编排 |
| `tests/` | 模块自己的最小回归测试 |

## 3. Hosted UI 是当前唯一正式 UI 契约

模块 UI 已经收口到纯页面声明。正式入口只有一类：

- `ui_extension.pages[]`

对应的声明方式也只有一类：

- `ui.declare_page`

而页面 schema 里能用的宿主控件只有：

- `Page`
- `Section`
- `Text`
- `Button`
- `DataTable`

这意味着：

- 模块不再导出 `PyQt6` 页面类
- 模块不再维护 `ui/` 页面目录
- `entry`、`core:data_table`、`ui.declare_data_table` 都不是正式事实

如果你要做概览页、说明页、KPI 看板、列表页、只读统计页或可编辑表格页，都是声明一个 `Page`，再把 `DataTable` 作为组件放进去。

## 4. CLI、宿主和 GitHub Release 各做不同的事

三者是分工关系，不是替代关系。

| 角色 | 正式职责 |
|---|---|
| CLI | 生成骨架、维护清单、跑 gate、打 ZIP、发布 Release、桥接宿主操作 |
| 宿主 | 加载模块、DevLink 联调、执行作业、渲染 Hosted UI、安装和升级模块 |
| GitHub Release | 正式模块 ZIP 的远端分发源 |

所以：

- 本地联调用 `host devlink`
- 正式安装用 ZIP
- 正式远端发布用 `release publish`
- 正式升级用 `host upgrade`

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
- 历史事件不混进快照数据

## CLI 主线和宿主主线分别是什么

### CLI 主线

```bash
module init -> task create -> workflow create -> page create -> check full -> package build -> release publish
```

### 宿主主线

```text
DevLink 挂载 -> ATM 创建作业 -> 执行 / 调试 -> ZIP 安装 -> host upgrade
```

这两条线会在模块 ZIP 和 `upgrade_source.repo` 上汇合。
