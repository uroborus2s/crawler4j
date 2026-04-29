# 模块结构

标准模块结构如下：

```text
demo_module/
├── __init__.py
├── module.yaml
├── pyproject.toml
├── data/
│   ├── sql/
│   │   ├── views/
│   │   │   └── *.sql
│   │   └── queries/
│   │       └── *.sql
│   └── seeds/
│       └── *.json
├── tasks/
│   └── *.py
├── workflows/
│   └── *.py
├── hooks/
│   └── *.py
├── env_selectors/
│   └── *.py
└── pages/
    ├── *.py
    └── <group>/
        └── *.py
```

## 每个位置负责什么

| 路径 | 职责 |
|---|---|
| `module.yaml` | 静态清单、`runtime_api`、工作流列表、Workflow 运行参数、默认工作流、左侧页面菜单元信息、`resource_pools`、`data` 数据契约 |
| `__init__.py` | 普通包入口，不再承载运行时装配 |
| `data/sql/views/*.sql` | 已注册统计视图的 SQL 文件 |
| `data/sql/queries/*.sql` | 已注册命名查询的 SQL 文件 |
| `data/seeds/*.json` | 已注册种子数据 |
| `tasks/*.py` | 单个任务声明与实现 |
| `workflows/*.py` | 单个工作流声明与实现 |
| `hooks/*.py` | 生命周期 Hook |
| `env_selectors/*.py` | 环境选择器 |
| `pages/*.py` / `pages/<group>/*.py` | Hosted UI 可路由页面注册、页面 schema 与处理函数 |

即使当前模块暂时不用数据能力，`module.yaml.data` 也必须存在，`data/` 目录也会由脚手架预先创建。

## 必须删除的旧结构

以下内容不是当前正式协议：

- `module_runtime.py`
- 根模块 `run()`
- `declare_ui()`
- `TaskScript`
- `TaskFlow`
- `ModuleAssembler`
- `@env_selector(...)`

如果旧模块还留着这些文件，迁移方式是把逻辑拆回固定目录，再补 `runtime_api: core-native-v1`。

## 根包要求

`__init__.py` 只需要保持为普通 Python 包。Core 会自行扫描子目录，不会从这里取运行时入口。

如果旧模块的根 `__init__.py` 被误删，或者你已经清理掉旧 `run()` / `declare_ui()` 残留，需要恢复到当前标准模板，可以直接执行：

```bash
uv run crawler4j module repair-init
```
