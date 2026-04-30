# 调试模块

模块调试主线固定为：

1. 在模块工程里先跑本地校验
2. 用 DevLink 把源码目录接到宿主
3. 在 ATM 先执行一次
4. 需要断点时再附加 `debugpy`

不要再单独维护模块根运行薄壳，也不要为调试临时发明第二套入口。

## 1. 先在模块工程里自检

最小命令集：

```bash
uv run crawler4j check structure
uv run crawler4j check full
uv run crawler4j task list
uv run crawler4j workflow list
uv run crawler4j page list
uv run crawler4j env-selector list
uv run crawler4j data list
```

这一层优先确认 5 件事：

- `module.yaml.runtime_api == core-native-v1`
- `default_workflow` 与 `module.yaml.workflows` 一致
- Core 规定的导出对象都存在
- `module.yaml.data`、`data/sql`、`data/seeds` 结构合法
- `PAGE.id`、同步 `load_handler`、表格 `query_handler`、环境选择器都能通过 gate

## 2. 注册 DevLink

切到宿主环境后：

```bash
uv run python -c "import src.core; print('ok: host runtime ready')"
uv run crawler4j host devlink add /abs/path/to/module
```

进入开发调试态的最小判据：

1. 模块详情页来源显示 `开发链接`
2. ATM 能选到这个模块
3. DevLink 模块可以执行 `执行一次`，也可以进入 `调试`

## 3. 先执行一次，再断点

第一次联调建议只保留：

- 1 个工作流
- 1 到 2 个任务
- 明确的阶段日志

推荐最小日志：

```python
ctx.state["phase"] = "login"
ctx.logger.info("进入登录阶段")
```

先用一次普通执行确认：

- 是否真的进入目标工作流
- 哪个任务先失败
- 是导入错误、清单错误，还是业务错误

## 4. 需要时再附加 IDE

```bash
uv run crawler4j host debug config
```

推荐顺序：

1. 在宿主里点击 `调试`
2. 看到会话进入 `waiting_for_attach`
3. 生成或刷新 IDE attach 配置
4. 从 IDE 附加
5. 再继续执行

## 5. 怎么查目录扫描问题

Core 的运行描述对象来自固定目录扫描，所以调试时按目录定位：

| 类型 | 先看什么 |
|---|---|
| 任务 | `tasks/*.py` 是否导出 `TASK`、`execute` |
| 工作流 | `workflows/*.py` 是否导出 `WORKFLOW`、`run` |
| Hook | `hooks/<name>.py` 是否导出 `handle` |
| 环境选择器 | `env_selectors/*.py` 是否导出 `SELECTOR`、`select` |
| 页面 | `pages/*.py`、`pages/<group>/*.py` 是否导出 `PAGE` 和对应 handler |

如果 `check full` 过了但宿主行为不对，优先确认：

- `TASK.name` / `WORKFLOW.name` / `SELECTOR.name` / `PAGE.id` 是否和预期一致
- 如果目标要出现在左侧菜单，`module.yaml.ui_extension.pages[]` 是否声明了它
- 如果目标只作为详情页或二级页，`pages/` 下是否存在对应 `PAGE.id`
- `default_workflow` 是否指向你正在调的工作流

## 6. 页面调试

页面问题优先按这条线查：

1. `page list` 是否能列出页面
2. 页面文件里的 `PAGE.schema` 是否有效
3. `load_handler` / `query_handler` 是否真实存在于同一文件
4. `query_handler` / `load_handler` 是否只通过 `ctx.db` 访问已注册的 `resource/view/query`
5. 模块详情页打开对应页面后是否拿到最新数据

页面现在直接来自 `pages/*.py`、`pages/<group>/*.py`。宿主不会再等待模块根入口去声明页面。

## 7. 环境选择器调试

环境选择器问题先看：

1. `env-selector list` 是否成功
2. `SELECTOR.name` 是否和运行模板里配置的一致
3. `select(context, candidates)` 返回的是 `env_id` 还是 `None`
4. 作业是否配置了 `resource_pool`

当 `resource_pool` 已配置时，返回 `None` 会进入等待语义；没配池时会按失败处理。

## 8. 数据契约调试

数据问题优先按这条线查：

1. `data list` / `module show` 能不能列出目标 `resources/views/queries/seeds`
2. `module.yaml.data` 里是否真的声明了目标资源、视图或命名查询
3. `data/sql/views/*.sql`、`data/sql/queries/*.sql` 是否只包含单条 `SELECT/WITH`
4. `{{resource:<id>}}` 占位符是否和 `source_resource_ids` 完全一致
5. 页面或任务代码是否还在调用旧 `db.declare_*`，或试图自己执行未注册 SQL

## 9. 常见误区

下面这些不是当前调试主线：

- 修改根包 `__init__.py` 试图接管运行时
- 新增 `module_runtime.py`
- 在运行时代码里 `import crawler4j_sdk`
- 试图通过 `declare_ui()` 注册页面
- 试图在运行时代码里调用 `db.declare_data_resource()` 或 `db.declare_db_view()`

如果你发现自己在排这些问题，说明模块还停留在旧协议。
