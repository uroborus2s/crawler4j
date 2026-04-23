# 构建模块

## 1. 初始化

```bash
uvx --from crawler4j-sdk crawler4j module init demo_module --repo example/demo_module
cd demo_module
```

## 2. 创建任务和工作流

```bash
uv run crawler4j task create example_task
uv run crawler4j workflow create main_workflow
```

任务文件必须导出：

- `TASK`
- `execute(ctx)`

工作流文件必须导出：

- `WORKFLOW`
- `run(ctx)`

## 3. 创建 Hook、环境选择器、页面和数据契约

```bash
uv run crawler4j hook create on_cleanup
uv run crawler4j env-selector create pick_ready
uv run crawler4j page create dashboard
uv run crawler4j data resource create accounts --storage-mode custom_table
uv run crawler4j data query create get_account_by_id --source accounts
uv run crawler4j data view create account_stats --source accounts
uv run crawler4j data seed create accounts_seed --resource accounts
```

CLI 会同步更新 `module.yaml.data`，并把 SQL / seed 骨架写到 `data/sql`、`data/seeds`。不要再在运行时代码里声明资源或视图。

## 4. 只从 contracts 导入

模块业务代码应该写成：

```python
from crawler4j_contracts import TaskContext, TaskResult, TaskSpec
```

不要再写：

- `from crawler4j_sdk import TaskContext`
- `TaskScript`
- `TaskFlow`
- `ModuleAssembler`

## 5. 运行前校验

```bash
uv run crawler4j check full
```

## 6. 打包

```bash
uv run crawler4j package build
uv run crawler4j package verify dist/demo_module-0.1.0.zip
```

## 7. 最重要的迁移判断

如果你的模块仍然依赖以下任意一项，说明还没迁移完：

- `module_runtime.py`
- 根包 `run()`
- `declare_ui()`
- `db.declare_data_resource(...)`
- `db.declare_db_view(...)`
- `TaskScript`
- `TaskFlow`
- `@env_selector(...)`
