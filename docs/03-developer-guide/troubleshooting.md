# 常见问题

这页按 `core-native-v1` 主线排查。先判断你卡在清单、目录扫描、页面、环境选择器，还是交付安装。

## 最短定位顺序

1. CLI 不通过：先跑 `uv run crawler4j check full`
2. Core 拒绝加载：先看 `module.yaml.runtime_api`
3. 任务或工作流找不到：先看固定导出是否存在
4. 页面不出来：先看 `pages/*.py` 和 `ui_extension.pages[]`
5. 数据或统计查询报错：先看 `module.yaml.data` 和 `data list`
6. 环境选择器不生效：先看 `env-selector list`
7. 安装失败：先看 ZIP 结构和 `upgrade_source.repo`

## Core 直接拒绝加载模块

优先确认：

- `module.yaml.runtime_api` 存在且值为 `core-native-v1`
- `default_workflow` 不为空
- `module.yaml.workflows` 里存在这个默认工作流

如果这些不满足，当前正式行为就是直接拒绝，不会做兼容桥。

## `check full` 不通过

优先确认：

- 当前目录下有 `module.yaml`
- `module.yaml.version` 是合法语义化版本
- `module.yaml.upgrade_source.repo` 是合法 `owner/repo`
- `module.yaml.data` 存在且 `resources/views/queries/seeds` 结构正确
- `tasks/`、`workflows/`、`pages/` 目录结构存在
- `data/sql`、`data/seeds` 文件路径和内容合法
- 运行时代码没有 import `crawler4j-sdk`

处理方式：

- 先修清单和导出，再继续写业务逻辑
- 不要带着已知 gate 错误去跑宿主联调

## 任务或工作流找不到

确认：

1. `tasks/*.py` 是否导出 `TASK` 和 `execute`
2. `workflows/*.py` 是否导出 `WORKFLOW` 和 `run`
3. `TASK.name` / `WORKFLOW.name` 是否和你实际调用的一致
4. `default_workflow` 是否指向真实存在的工作流

## 页面是空白

确认：

1. `module.yaml.ui_extension.pages[]` 是否存在目标页面
2. `pages/<page>.py` 是否导出 `PAGE`
3. `PAGE.schema` 顶层是否是 `Page`
4. `load_handler` / `query_handler` 是否真实存在于同一文件
5. `uv run crawler4j check full` 是否通过

页面现在直接来自 `PAGE.schema`，不是运行时再声明。

## 表格没有数据

确认：

1. `DataTable.data_source.type` 是否是 `binding`、`rows` 或 `query_handler`
2. `load_handler` 返回值里是否真的有绑定字段
3. `query_handler` 的签名是否是 `(context, table_id, query, params=None)`
4. `db.get_record` / `db.list_records` / `db.run_query` / `db.query_view` 返回值是否真的是你页面期望的结构

## 数据契约或查询报错

确认：

1. `module.yaml.data` 是否真的声明了目标 `resource/view/query`
2. `data list` / `module show` 是否能看到对应数量
3. `view` / `query` 是否只引用 `custom_table` 资源
4. SQL 文件是否位于 `data/sql/views`、`data/sql/queries`，且只包含单条 `SELECT/WITH`
5. `{{resource:<id>}}` 是否和 `source_resource_ids` 完全一致
6. 运行时代码是否还在调用旧 `db.declare_*`，或试图自己执行未注册 SQL

## 环境选择器不生效

确认：

1. `env-selector list` 是否能列出来
2. `env_selectors/*.py` 是否导出 `SELECTOR` 和 `select`
3. `SELECTOR.name` 是否和运行模板里的 `selector_name` 一致
4. 返回 `None` 时，作业是否真的配置了 `resource_pool`

## 运行时导入失败

重点检查：

- 业务代码是否还在 `from crawler4j_sdk import ...`
- 是否仍然保留旧运行薄壳并让新代码从它间接导入
- 是否把只在开发态存在的包当成运行时依赖

运行时模块只能依赖 `crawler4j-contracts`。

## 安装或升级失败

确认：

1. ZIP 是否只有一个根目录
2. 根目录下是否存在 `module.yaml`
3. `module.yaml.upgrade_source.repo` 是否合法
4. `module.yaml.data` 是否存在并符合当前协议
5. ZIP 是否仍然混入 legacy 结构

必要时先执行：

```bash
uv run crawler4j package verify dist/<module>-<version>.zip
```
