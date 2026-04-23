# 构建模块

这一页回答一个问题：标准模块应该怎么从“目录骨架”写成“可联调、可交付、可升级”的业务模块。

最短答案是：

- 用 `task` 写原子动作
- 用 `workflow` 写流程编排
- 用 `module_runtime.py` 接宿主生命周期、环境选择器和 Hosted UI
- 先用 `check` 跑通模块工程和 DevLink 联调，再用 `package`、`release`、`host` 收口成正式交付物

## 开发顺序固定按这条线走

推荐顺序不要改：

1. `module init`
2. `task create`
3. `workflow create`
4. `page create`
5. 补 `module.yaml`、`tasks/`、`workflows/`、`module_runtime.py`
6. `check full`
7. DevLink 联调
8. `package build`
9. `release publish`
10. `host upgrade`

## 先把命令树映射到开发动作

| 命令组 | 你在开发时什么时候用 |
|---|---|
| `task` | 新增一个原子业务动作时 |
| `workflow` | 新增一个业务流程或默认工作流时 |
| `page` | 需要概览页、列表页、看板、说明页或表格页时 |
| `env-selector` | 需要 ATM 的“选择环境”模式时 |
| `config` | 需要更新默认配置模板时 |
| `check` | 每完成一个阶段就跑 gate |
| `package` | 准备正式交付时 |
| `release` | 准备把 ZIP 发布到 GitHub Release 时 |
| `host` | 在宿主里联调、安装或升级模块时 |

## `module_runtime.py` 只做宿主接缝

模块开发的第三个落点是 `module_runtime.py`。这里的职责固定为三类：

1. lifecycle hook
2. `@env_selector(...)`
3. Hosted UI 页面声明

最小签名边界先记住：

| 名称 | 当前约束 |
|---|---|
| `declare_ui(context)` | 同步函数，必须可重放 |
| `load_*_page(context, page_id, params=None)` | 同步函数，返回结构化字典 |
| `query_*_table(context, table_id, query, params=None)` | 同步函数，返回表格查询结果 |
| `ctx.tools.call(...)` | 统一宿主能力边界 |

### Hosted UI

当前 UI 正式写法只有一种：在 `module_runtime.py` 里声明页面。

最小骨架：

```python
def declare_ui(context: TaskContext):
    _declare_dashboard_page(context)
    _declare_accounts_page(context)
    return None
```

适合：

- KPI
- 说明文案
- 只读表格
- 可编辑表格
- 页面按钮

入口写法：

- `module.yaml.ui_extension.pages[]`
- `context.tools.call("ui.declare_page", ...)`

`DataTable` 现在只是页面组件。列表展示、分页、搜索、排序、行点击都在页面 schema 里声明，数据由 `load_handler` 或内联表格 `query_handler` 提供。

## 把配置、运行态、快照数据和历史事件分开

| 类别 | 正式入口 | 用法 |
|---|---|---|
| 持久配置 | `ctx.get_config()` / `ctx.config` | 读模块级和 workflow 级配置 |
| 运行态元数据 | `ctx.runtime` | 读 `workflow`、`params`、`devel_mode`、`creation_params` |
| 单次执行状态 | `ctx.state` | 保存一次执行内的小体量临时状态 |
| 当前快照数据 | `db.list_records` / `db.replace_records` | 保存当前列表、当前结果集 |
| append-only 历史 | `db.append_event` / `db.query_events` | 保存状态迁移、操作痕迹、事件历史 |

不要混用：

- 不要把 `workflow`、`params` 写进配置
- 不要把长期数据塞进 `ctx.state`
- 不要把历史事件混进快照数据

## 每完成一个阶段就跑 gate

建议最少用这几档校验：

```bash
uv run crawler4j check structure
uv run crawler4j check release
uv run crawler4j check full
```

直接理解成：

- `structure`：骨架、清单和页面入口格式
- `release`：版本、升级源、默认配置等发布前提
- `full`：模块、task、workflow、Hosted UI 的完整导入和声明 gate
