# 调试模块

> 版本绑定：本文只适用于 0.4.x SDK / Contracts 与 Core 0.4.0。0.4.x 调试链不兼容 0.3.x DevLink 开发模式。

0.4.0 调试主线：

1. 在模块工程跑装饰器扫描
2. 生成 manifest lock
3. 用 DevLink 接入宿主
4. 在运行模板里配置对象装配
5. 先执行一次，再附加调试器

不要为调试新增第二套运行入口。

## 本地自检

```bash
uv run crawler4j check structure
uv run crawler4j check full
uv run crawler4j manifest lock
uv run crawler4j interface list
uv run crawler4j component list
uv run crawler4j workflow list
uv run crawler4j page-action list
uv run crawler4j data list
```

优先确认：

- `module.yaml.runtime_api == core-native-v2`
- 装饰器能被扫描
- workflow inject 目标存在
- component implements 目标存在
- 对象图无环
- page action 是函数或 async 函数
- 数据字段没有宿主保留名
- lock 与当前源码一致

## DevLink

切到宿主环境：

```bash
uv run python -c "import src.core; print('ok: host runtime ready')"
uv run crawler4j host devlink add /abs/path/to/module
```

DevLink 注册必须执行和 `check full` 同级的扫描诊断。阻断错误不得登记为可运行模块。

## 对象装配问题

如果运行模板打不开对象配置区，按顺序检查：

1. workflow 是否有 `@workflow`
2. workflow 的 `inject` 是否为空或写错；使用注解写法时，检查 `__init__` 参数上的 `object_inject(...)`
3. interface 是否至少有一个 `@component(implements=...)`
4. component 的 `inject` 是否引用不存在的 interface 或 object；使用注解写法时，检查类属性上的 `object_inject(...)`
5. 对象图是否有环

如果运行时报构造失败，重点看：

- 构造函数参数名是否和 `inject.name` 一致
- 构造函数参数名是否和 `parameters[].name` 一致
- `object_param(...)` 是否声明在真正需要普通值的 component 上
- 运行模板是否保存了必填对象参数

## workflow 参数误用

下面这些都是错误方向：

- 在 `@workflow` 上声明 `parameters`
- 在模块清单里继续给 workflow 加普通参数字段
- 在 `ctx.runtime.params` 读取对象选择
- 把业务配置塞进 workflow 构造函数

修复方式：

1. 把普通参数移到对应 component 的 `parameters` 或 `object_param(...)` 注解
2. 让 workflow 注入 orchestrator
3. 在 orchestrator 内使用具体对象

## 数据诊断

如果数据扫描失败，先看错误字段来源：

- 显式 schema
- 类注解字段
- index
- query output schema

宿主保留字段会直接阻断：

- `created_at`
- `updated_at`
- `create_at`
- `update_at`

不要为了通过校验改成拼写近似字段。来源系统时间戳要写成业务名，例如 `source_created_at`。

## 页面调试

页面问题按这条线查：

1. `page list` 是否能列出页面
2. `@page.schema` 顶层是否是 `Page`
3. 被 `@page` 装饰的 load handler 是否真实存在
4. `DataTable.data_source` 是否引用已声明数据表或 handler
5. 页面动作是否引用已扫描的 `@page_action`

如果页面能打开但表格没数据，先在 handler 里直接打印 `ctx.db.from_("...").limit(5).execute()` 的结果。

## 断点调试

```bash
uv run crawler4j host debug config
```

推荐顺序：

1. 普通执行一次
2. 确认对象装配和数据扫描都通过
3. 在宿主点击调试
4. 看到 `waiting_for_attach`
5. 从 IDE attach

## 常见误区

- 改根包 `__init__.py` 试图接管运行时
- 手写 manifest lock
- 让 workflow 接收普通参数
- 把对象实例放到模块全局变量
- 在 page action 中保存跨任务状态
- 运行时代码 import `crawler4j_sdk`
- 使用 `ctx.tools.call("db.*")`
