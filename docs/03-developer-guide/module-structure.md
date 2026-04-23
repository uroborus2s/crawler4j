# 模块结构

当前模块源码布局已经正式收口为一套固定结构。不要再把模块 UI、Hook、环境选择器都揉进 `module_runtime.py`，也不要再为模块 UI 单独约定别的目录。

## 标准目录

`crawler4j module init` 生成的标准模块目录如下：

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
├── workflows/
├── pages/
├── hooks/
├── env_selectors/
└── tests/
```

正式安装包仍然输出到：

```text
dist/
└── hotel_demo-0.1.0.zip
```

## 路径职责

| 路径 | 正式职责 |
|---|---|
| `__init__.py` | SDK 托管模块根入口，负责 `assembler`、`run()` 和把 `module_runtime.py` 暴露给宿主 |
| `module.yaml` | 唯一静态清单，声明模块身份、工作流、页面导航、默认配置和升级来源 |
| `module_runtime.py` | 宿主接缝薄壳，只负责把 `pages/`、`hooks/`、`env_selectors/` 暴露给宿主 |
| `tasks/` | 原子业务任务 |
| `workflows/` | 业务流程编排 |
| `pages/` | Hosted UI 页面，一页一个文件 |
| `hooks/` | 生命周期 Hook，一类 Hook 一个文件 |
| `env_selectors/` | `@env_selector(...)` 选择器，一个选择器一个文件 |
| `tests/` | 模块自测 |

## `module.yaml` 只保留导航事实

Hosted UI 的静态入口现在只有 `ui_extension.pages[]`，每一项只允许：

- `id`
- `label`
- `icon`

示例：

```yaml
ui_extension:
  pages:
    - id: dashboard
      label: 运营看板
      icon: 📄
    - id: accounts
      label: 账号列表
      icon: 📄
```

页面 schema、页面加载逻辑、表格查询逻辑都不写在 `module.yaml` 里。

## `module_runtime.py` 必须保持薄壳

当前正式写法是：

```python
from __future__ import annotations

import importlib
from typing import Any

from crawler4j_sdk import TaskContext

_hooks = importlib.import_module(f"{__package__}.hooks")
_pages = importlib.import_module(f"{__package__}.pages")
_env_selectors = importlib.import_module(f"{__package__}.env_selectors")


def declare_ui(context: TaskContext):
    return _pages.declare_pages(context)


def __getattr__(name: str) -> Any:
    for namespace in (_hooks, _pages, _env_selectors):
        if hasattr(namespace, name):
            return getattr(namespace, name)
    raise AttributeError(name)
```

它只承担三件事：

- 暴露 `declare_ui()`
- 暴露 Hook、页面 handler、环境选择器
- 维持宿主可发现的模块级符号

不要把业务流程、数据转换、页面大段 schema 继续堆回这个文件。

## 页面怎么组织

正式规则是“一页一文件”，统一放在 `pages/`：

```text
pages/
├── __init__.py
├── dashboard.py
├── accounts.py
└── account_detail.py
```

每个页面文件至少包含：

- `PAGE_ID`
- `PAGE_DECLARER`
- `declare_<page_id>_page(context)`
- `build_<page_id>_page_schema()`
- `load_<page_id>_page(context, page_id, params=None)`

如果页面里有内联表格，再额外实现：

- `query_<table_id>(context, table_id, query, params=None)`

`pages/__init__.py` 负责自动导出这些函数并聚合 `declare_pages(context)`。

## 子页面怎么处理

当前宿主左侧导航仍然是平铺菜单，没有正式的父子菜单协议。所以现在只有两种正式做法：

1. 同一页面内切换详情态
   场景：列表页点开详情、主从视图、同一导航项下的局部切换。
   做法：继续使用同一个 `page_id`，通过 `open_page(page_id, params)` 传参，让 `load_handler` 按 `params` 渲染不同状态。

2. 拆成多个独立页面
   场景：它们都需要成为左侧菜单里的独立入口。
   做法：给每个页面单独声明 `page_id`，分别出现在 `ui_extension.pages[]` 里。

当前不要假设存在“隐藏子页”“父子菜单”或“目录树导航”。

## Hook 和环境选择器

生命周期 Hook 统一放在 `hooks/`：

```text
hooks/
├── __init__.py
├── prepare_env.py
├── init_env.py
├── before_run.py
├── on_success.py
├── on_failure.py
├── on_timeout.py
└── on_cleanup.py
```

环境选择器统一放在 `env_selectors/`：

```text
env_selectors/
├── __init__.py
├── return_none.py
├── random_ready.py
└── pick_ready.py
```

这里目录名明确使用 `env_selectors/`，不要用 `selectors/`。模块根目录直接存在 `selectors/` 时，容易和 Python 标准库 `selectors` 冲突，影响 CLI 和导入链路。

## CLI 会生成什么

当前正式命令如下：

```bash
uv run crawler4j module init hotel_demo --repo your-org/hotel_demo
uv run crawler4j page create dashboard
uv run crawler4j hook create on_cleanup
uv run crawler4j env-selector create pick_ready
```

它们对应的结果是：

- `module init`
  生成 `pages/`、`hooks/`、`env_selectors/` 目录和默认薄壳。
- `page create <page_id>`
  创建 `pages/<page_id>.py`，并把页面入口写入 `module.yaml.ui_extension.pages[]`。
- `hook create <hook_name>`
  创建或重建 `hooks/<hook_name>.py`。
- `env-selector create <name>`
  创建 `env_selectors/<name>.py`。

## 约束总结

当前模块 UI 的正式边界只有一条：

- 宿主只负责渲染纯 UI 组件和提供通用能力
- 模块负责页面 schema、页面数据和表格查询
- `module_runtime.py` 只做接缝薄壳
- 页面、Hook、环境选择器都拆到独立文件

如果模块规模继续增大，下一步也应当在这套目录内继续细化，而不是重新引入第二套 UI 目录协议。
