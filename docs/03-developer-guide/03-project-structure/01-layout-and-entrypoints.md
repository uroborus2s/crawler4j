# 3.1 目录结构与入口

## 标准模块项目结构

CLI 生成的规范化模块项目，采用 **Tasks / Workflows / Data / UI** 四层分层设计：

```text
hotel_demo/
├── __init__.py           # 模块根入口（自动托管薄壳，Shim）
├── module_runtime.py     # [扩展] 运行时自定义逻辑点（Hooks、手动注册）
├── module.yaml           # 模块清单（元数据与能力声明）
├── pyproject.toml        # 开发环境依赖配置
├── tasks/                # [任务层] 原子操作脚本 (TaskScript)
│   ├── __init__.py
│   └── example_task.py
├── workflows/            # [编排层] 业务逻辑流 (TaskFlow)
│   ├── __init__.py
│   └── main_workflow.py
├── data/                 # [数据层] 数据模型与 Schema
│   ├── __init__.py
│   └── models.py
├── ui/                   # [界面层] 配置 Schema 与自定义 UI
│   ├── __init__.py
│   ├── config_schema.json # 声明式配置
│   └── dashboard.py      # 代码型 UI (micro_app)
├── utils/                # [工具层] 内部复用逻辑
│   ├── __init__.py
│   └── helpers.py
└── tests/                # [测试层] 模块单元测试
    ├── __init__.py
    └── test_tasks.py
```

## 各层职责定义

### `tasks/` (任务层)
原子任务单元。每个文件应只负责一个明确的操作（如：登录、解析单页数据）。它直接与 `TaskContext.page` 和 `TaskContext.http` 交互。

### `workflows/` (编排层)
业务流程引擎。负责调用多个任务，处理任务间的逻辑判断、循环和状态传递。它不应直接处理底层的 DOM 解析。

### `data/` (数据层)
定义模块使用的 Pydantic 模型。这确保了模块内数据的强类型约束，并方便 Core 导出数据。

### `ui/` (界面层)
收纳模块的所有界面元素。
*   `config_schema.json` 定义了作业启动时的参数表单。
*   代码型 UI (`micro_app`) 则允许开发者编写基于 PyQt 的复杂监控或管理面板。

### `utils/` (工具层)
存放模块内的公共辅助函数，严禁在 `tasks` 之间通过相对路径互相引用逻辑，应统一抽取至此。

## 运行时调用顺序与扩展点

### 1. 根入口薄壳 (`__init__.py`)
从 SDK 2.1.0 开始，该文件是固定的薄壳，它通过 `ModuleAssembler` 自动完成组件发现和分发。**不建议手动修改此文件。**

### 2. 自定义运行时 (`module_runtime.py`)
如果你需要扩展模块级逻辑，应使用 `module_runtime.py`。支持的扩展点包括：

- **生命周期 Hooks:** `prepare_env`, `init_env`, `before_run`, `on_success`, `on_failure`, `on_timeout`, `on_cleanup`
- **默认工作流覆盖:** `DEFAULT_WORKFLOW`
- **手动注册组件:** `TASK_SCRIPTS`, `WORKFLOWS`

宿主的执行顺序是：

```text
module_runtime.prepare_env
-> module_runtime.init_env
-> module_runtime.before_run
-> assembler (discovery & dispatch)
-> workflow.run / task.execute
-> module_runtime.on_success / on_failure / on_timeout
-> ATM env action
-> module_runtime.on_cleanup
```

其中有两个边界需要记住：

- `TaskScript` / `TaskFlow` 本身只有单一入口方法：`execute(ctx)` 或 `run(ctx)`
- `on_cleanup` 发生在 ATM 完成环境动作之后；模块可以通过 `ctx.runtime["env_action"]` 判断环境最终是 `recycle`、`keep_alive` 还是 `destroy`

如果模块需要影响 ATM 的后续流程，例如销毁环境、等待人工确认、直接标记失败，应通过 `TaskSignal` 发信号给 ATM，而不是让脚本或工作流直接操作 REM。

这里固定一条正式规则：

- `on_cleanup` 是任务终态清理 hook，不是环境删除 hook
- 只要任务已经建立 `TaskContext` 并进入终态，ATM 都会执行 `on_cleanup`
- 是否真的删除了环境，必须通过 `ctx.runtime["env_action"]` 判断，不能靠 `on_cleanup` 是否被调用来判断

## 命名建议

从运行时角度，不是所有名称都必须完全一致；但从维护成本角度，强烈建议保持下面三者一致：

1. 模块目录名
2. Python 包名
3. `module.yaml.name`

例如：

```text
hotel_demo/
module.yaml.name = hotel_demo
```

这样在 DevLink、任务运行配置、调试、安装和错误排查时最不容易出错。

## 第一次开发模块时，哪些文件最不能随便动

如果你是小白，建议先不要随便删除或重构下面这些文件：

1. 根 `__init__.py`
2. `module.yaml`
3. `tasks/__init__.py`
4. `workflows/__init__.py`

原因很简单：这些文件不是“为了好看”，而是直接参与模块发现、导入和运行。

## 看完这一页后的最小结论

这一页看完后，至少记住下面三句话：

1. 模块目录结构本身就是契约的一部分。
2. 根 `__init__.py` 才是宿主最终进入的运行入口。
3. `pyproject.toml` 属于模块开发环境，不等于宿主运行环境。
