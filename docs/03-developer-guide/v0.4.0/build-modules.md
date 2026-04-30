# 构建模块

> 版本绑定：本文只适用于 0.4.x SDK / Contracts 与 Core 0.4.0。0.4.x SDK 是破坏性升级线，不兼容 0.3.x 的 CLI 命令、模板或模块开发模式。

## 1. 初始化

```bash
uvx --from crawler4j-sdk crawler4j module init demo_module \
  --repo example/demo_module \
  --runtime-api core-native-v2

cd demo_module
uv sync
```

## 2. 创建装饰器骨架

```bash
uv run crawler4j interface create labor
uv run crawler4j component create api_labor --implements labor
uv run crawler4j workflow create main_workflow
uv run crawler4j page-action create open_login_page
uv run crawler4j data table create accounts
uv run crawler4j data query create ready_accounts --source accounts
```

这些命令写 Python 装饰器模板，不再把运行能力写入 `module.yaml`。

## 3. 写对象依赖

对象依赖写在 `inject` 里：

```python
@component(
    name="account_orchestrator",
    implements="orchestrator",
    inject=[
        {"name": "labor", "type": "interface", "target": "labor"},
    ],
)
class AccountOrchestrator:
    def __init__(self, labor):
        self.labor = labor
```

对象参数写在 `parameters` 里：

```python
@component(
    name="api_labor",
    implements="labor",
    parameters=[
        {"name": "base_url", "type": "string", "required": True},
    ],
)
class ApiLabor:
    def __init__(self, base_url: str):
        self.base_url = base_url
```

## 4. 写 workflow

```python
@workflow(
    name="main_workflow",
    inject=[
        {"name": "orchestrator", "type": "interface", "target": "orchestrator"},
    ],
)
class MainWorkflow:
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator

    async def run(self, ctx):
        return await self.orchestrator.run(ctx)
```

workflow 不接收普通参数。运行模板只保存对象实现选择和对象参数。

## 5. 写 page action

```python
@page_action(name="open_login_page")
async def open_login_page(ctx, url: str):
    await ctx.page.goto(url)
    return {"status": "opened"}
```

page action 是页面操作纯函数。不要在这里保存账号状态、缓存或跨任务对象。

## 6. 写数据契约

```python
@data_table(
    name="accounts",
    schema=[
        {"name": "account_id", "type": "string", "required": True},
        {"name": "status", "type": "string"},
    ],
)
class Accounts:
    pass
```

字段名不要使用宿主保留字段：

- `created_at`
- `updated_at`
- `create_at`
- `update_at`

来源系统时间戳用业务字段名，例如 `source_created_at`。

## 7. 校验

```bash
uv run crawler4j check full
uv run crawler4j manifest lock
```

`check full` 至少检查：

- `runtime_api == core-native-v2`
- 装饰器元数据合法
- 名称唯一
- inject 目标存在
- 对象图无环
- workflow 没有 parameters
- component 参数类型合法
- page action 是函数或 async 函数
- 数据字段、索引、query output 不使用宿主保留字段
- `module.yaml` 没有 v2 禁止字段

## 8. 打包

```bash
uv run crawler4j check release
uv run crawler4j package build
uv run crawler4j package verify dist/demo_module-0.1.0.zip
```

打包阶段会复用扫描诊断，防止过期 lock 或保留字段冲突进入安装包。
