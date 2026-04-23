# 模块结构

标准模块结构如下：

```text
demo_module/
├── __init__.py
├── module.yaml
├── pyproject.toml
├── tasks/
│   └── *.py
├── workflows/
│   └── *.py
├── hooks/
│   └── *.py
├── env_selectors/
│   └── *.py
└── pages/
    └── *.py
```

## 每个位置负责什么

| 路径 | 职责 |
|---|---|
| `module.yaml` | 静态清单、`runtime_api`、工作流列表、默认工作流、页面导航元信息 |
| `__init__.py` | 普通包入口，不再承载运行时装配 |
| `tasks/*.py` | 单个任务声明与实现 |
| `workflows/*.py` | 单个工作流声明与实现 |
| `hooks/*.py` | 生命周期 Hook |
| `env_selectors/*.py` | 环境选择器 |
| `pages/*.py` | Hosted UI 页面与页面处理函数 |

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
