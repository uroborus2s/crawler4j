# SDK 与 CLI 参考

`crawler4j-sdk` 现在只面向开发阶段。

## 命令入口

- 模块项目内：`uv run crawler4j ...`
- 不安装直接用：`uvx --from crawler4j-sdk crawler4j ...`
- 在 Core 源码仓验证本地 CLI：`uv run python -m crawler4j_sdk.cli.commands ...`

## 模块工程命令

| 命令组 | 关键命令 | 主要输出 |
|---|---|---|
| `module` | `module init` `module show` `module repair-init` `module set repo/version/default-workflow` | 模块根目录与 `module.yaml` |
| `task` | `task create` `task list` | `tasks/<name>.py` |
| `workflow` | `workflow create` `workflow list` | `workflows/<name>.py` 与 `module.yaml.workflows` |
| `page` | `page create` `page list` | `pages/<page>.py` 或 `pages/<group>/<file>.py`；`ui_extension.pages[]` 只控制左侧菜单 |
| `hook` | `hook create` `hook list` | `hooks/<hook>.py` |
| `env-selector` | `env-selector create` `env-selector list` | `env_selectors/<name>.py` |
| `data` | `data list` `data resource create` `data view create` `data query create` `data seed create` | `module.yaml.data`、`data/sql/*`、`data/seeds/*` |
| `config` | `config show` `config set ...` `config lint` | `module.yaml.config_defaults` |
| `check` | `check structure` `check release` `check full` | 本地校验 gate |
| `package` | `package build` `package verify` | ZIP 包 |
| `release` | `release status` `release check-remote` `release publish` | 发布辅助 |
| `host` | `host devlink ...` `host install ...` `host upgrade ...` `host debug config` | 宿主联调辅助 |

## `module init`

初始化后会生成：

- `runtime_api: core-native-v1`
- `default_workflow`
- `module.yaml.data.resources/views/queries/seeds`
- contracts-only 运行时依赖
- sdk-only 开发依赖
- `tasks/`、`workflows/`、`hooks/`、`env_selectors/`、`pages/`
- `data/sql/views`、`data/sql/queries`、`data/seeds`

不会再生成：

- `module_runtime.py`
- 根包运行薄壳
- 任何兼容桥

`module show` 现在还会额外打印 `resources/views/queries/seeds` 数量，方便你快速确认当前模块的数据契约规模。

## `module repair-init`

当旧模块的根 `__init__.py` 被手改脏、误删，或者你已经把旧 `run()` / `declare_ui()` / `TaskScript` 残留拆回标准目录后，可以执行：

```bash
uv run crawler4j module repair-init
```

这个命令只会按当前模板重建模块根 `__init__.py`，显示名优先取 `module.yaml.display_name`；它不会改写 `module.yaml`、任务、工作流、Hook、环境选择器或页面源码。

## 数据契约命令

- `data resource create <name> [--storage-mode managed_dataset|custom_table]`
- `data view create <view_id> --source <resource_id>`
- `data query create <query_id> --source <resource_id>`
- `data seed create <seed_id> --resource <resource_id>`
- `data list`

当前约束：

- `view` / `query` 只允许引用已经登记的 `custom_table` 资源
- SQL 文件会固定写到 `data/sql/views`、`data/sql/queries`
- `seed` 固定写到 `data/seeds/*.json`

## `check full`

当前会校验：

- `runtime_api == core-native-v1`
- 目录结构完整
- `module.yaml.data` 存在且四段都是合法数组
- `data.resources[]` 只允许 `id/storage_mode/record_key_field/schema/indexes/cleanup_policy/joins`；不要在资源项里写 `resource_id`
- `default_workflow` 与 `module.yaml.workflows` 一致
- `module.yaml.workflows[].parameters[]` 的参数名、类型、枚举选项和数字边界合法
- `TaskSpec/WorkflowSpec/EnvSelectorSpec/PageSpec` 导出存在
- 任务、工作流、环境选择器的文件名与声明名一致
- `ui_extension.pages[]` 中的菜单页面存在对应页面文件；所有页面文件的 `PAGE.id` 为唯一扁平 snake_case
- 页面 `load_handler` 必须是同步函数；内联 `query_handler` 需要存在且签名兼容
- 视图/命名查询只引用 `custom_table` 资源
- `data/sql` / `data/seeds` 文件路径、格式和占位符合法
- SQL 只能是单条 `SELECT/WITH`，且 `{{resource:<id>}}` 必须与 `source_resource_ids` 一致
- legacy `ui/`、`config_schema.json`、`strategy.yaml` 已清理

## 环境选择器

当前正式写法只有一种：

```python
from crawler4j_contracts import EnvCandidate, EnvSelectorSpec, TaskContext

SELECTOR = EnvSelectorSpec(name="pick_ready")

def select(context: TaskContext, candidates: list[EnvCandidate]):
    ...
```
