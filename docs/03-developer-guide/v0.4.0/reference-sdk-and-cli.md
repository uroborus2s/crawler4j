# SDK 与 CLI 参考

> 版本绑定：本文列出 0.4.x SDK 命令。0.4.x SDK 只服务 Core 0.4.0 / `core-native-v2`，不兼容 0.3.x 的命令、模板或开发模式。

`crawler4j-sdk` 在 0.4.0 只面向 0.4.0 模块开发阶段。开发或维护 0.3.x 模块必须使用 0.3.x SDK。

## 命令入口

- 模块项目内：`uv run crawler4j ...`，用于 `module`、装饰器骨架、`manifest`、`check`、`package` 和 `release` 等模块工程命令
- 不安装直接用：`uvx --from crawler4j-sdk crawler4j ...`
- Core 源码仓或已安装宿主环境内：`uv run crawler4j host ...`，用于 DevLink、ZIP 安装、升级和调试配置；这些命令需要宿主运行时，不能在只有 SDK/Contracts 依赖的模块工程里当作普通模块命令执行
- 在 Core 源码仓验证本地 CLI：`uv run python -m crawler4j_sdk.cli.commands ...`

## 模块工程命令

| 命令组 | 关键命令 | 主要输出 |
|---|---|---|
| `module` | `module init` `module show` `module set repo/version` | 0.4.0 模块根目录与 `module.yaml` |
| `interface` | `interface create` `interface list` | `@interface` 模板 |
| `component` | `component create` `component list` | `@component` 模板 |
| `workflow` | `workflow create` `workflow list` | `@workflow` 模板 |
| `page-action` | `page-action create` `page-action list` | `@page_action` 函数 |
| `ui-action` | `ui-action create` `ui-action list` | `@ui_action` 函数 |
| `page` | `page create` `page list` | `@page` Hosted UI 页面 |
| `data` | `data table create [--storage-mode custom_table\|managed_dataset]` `data view create` `data list` | `@data_table` / `@data_view` |
| `candidate` | `candidate create` `candidate list` | `@env_candidates` 同步纯函数 |
| `cleanup` | `cleanup create` `cleanup list` | `@env_cleanup_candidates` 同步纯函数 |
| `config` | `config show` `config set module --file <yaml>` `config lint` | `module.yaml.config_defaults` |
| `manifest` | `manifest lock` | `.crawler4j/manifest.lock.json` |
| `check` | `check structure` `check release` `check full` | 本地校验 gate |
| `package` | `package build` `package verify` | ZIP 包 |
| `release` | `release status` `release check-remote` `release publish` | 发布辅助 |
| `host` | `host devlink ...` `host install ...` `host upgrade ...` `host debug config` | 宿主联调辅助；在 Core 源码仓或已安装宿主环境执行 |

## `module init`

```bash
uvx --from crawler4j-sdk crawler4j module init
```

无参模式会交互式询问模块包名和升级源仓库，其余选项使用默认值：

```text
模块包名（snake_case）: demo_module
升级源 GitHub 仓库（owner/repo）: example/demo_module
```

需要脚本化或显式控制时仍可完整传参：

```bash
uvx --from crawler4j-sdk crawler4j module init demo_module \
  --repo example/demo_module \
  --runtime-api core-native-v2
```

初始化后应生成：

- `runtime_api: core-native-v2`
- contracts-only 运行时依赖
- sdk-only 开发依赖
- 装饰器目录骨架
- `.crawler4j/` 目录
- 页面目录

不会生成旧运行薄壳或重复运行能力清单。

0.4.x SDK 也不会生成或维护 0.3.x 旧开发入口，包括：

- `crawler4j task create`
- `crawler4j env-selector create`
- `crawler4j hook create`
- `crawler4j data resource create`
- `crawler4j data seed create`
- `crawler4j module set default-workflow`

## `workflow create`

普通 workflow：

```bash
uv run crawler4j workflow create booking_sync
```

已有环境导入 workflow：

```bash
uv run crawler4j workflow create import_existing_env \
  --host-scenario existing_env_import
```

`--host-scenario existing_env_import` 会在生成的装饰器上写入 `host_scenarios=["existing_env_import"]`。宿主“从已有环境导入”对话框和导入服务只识别这个显式声明；未声明的普通 workflow 不会作为导入入口。

## `check full`

0.4.0 会校验：

- `runtime_api == core-native-v2`
- 装饰器参数、类属性注解和 `__init__` 参数注解元数据字段合法
- 名称为小写 snake_case
- interface / component / workflow / data table / data view 名称唯一
- interface 至少有实现
- workflow inject 目标存在
- component inject 目标存在
- object graph 无环
- component parameters 类型合法；`object_param(...)` 可从 `str/int/float/bool`、`Literal[...]`、`list[T]`、`dict[str, T]`、`Optional[T]` / `T | None`、`datetime.date/datetime/time`、`pathlib.Path` 注解推断类型
- component parameters 支持 `string/text/integer/number/boolean/enum/array/object/json/date/datetime/time/url/path/secret`；`array` 可用 `item_schema` 校验元素，`object` 可用 `schema.fields` / `schema.additional_type` 校验结构
- workflow 没有 parameters
- page 使用 `@page(...)` 装饰函数；`menu=True` 进入左侧菜单，`menu=False` 只注册可路由页面
- page action 是函数或 async 函数
- ui action 是函数或 async 函数
- data table 字段、索引、data view schema 不使用宿主保留字段
- `module.yaml` 不含 v2 禁止字段
- 运行时代码没有依赖 `crawler4j-sdk`
- `.crawler4j/manifest.lock.json` 存在且与当前源码一致

## `manifest lock`

```bash
uv run crawler4j manifest lock
```

生成 `.crawler4j/manifest.lock.json`。

生成前会复用 full gate 的装饰器、对象图和运行时代码诊断，但不要求已有 lock。阻断错误存在时不会写 lock。正常顺序是 `check structure` -> `manifest lock` -> `check full`。

manifest lock 的文件完整性列表会先跳过 `.git/`、`.venv/`、`.pytest_cache/`、`.ruff_cache/`、`build/`、`dist/`、`*.egg-info/` 等本地开发和构建目录。忽略目录里的解释器 symlink 不会阻断 DevLink 或 lock 生成；未被忽略、会进入模块文件集合的 symlink 仍会被拒绝。

## 模块打开阶段诊断

SDK 在这些入口必须执行同一套诊断：

- 模块项目打开
- DevLink 注册
- `crawler4j manifest lock`
- `crawler4j check full`
- `crawler4j package build`

保留字段冲突必须在开发阶段阻断，不能等到运行时失败。

源码目录扫描和打包文件收集使用同一套忽略路径判断：先排除不会进入 manifest/ZIP 的本地目录，再对真实模块文件执行 symlink 拒绝和路径越界检查。ZIP 包验证仍然拒绝 ZIP 内 symlink 和路径穿越。

## 迁移边界

当前 0.4.x SDK 没有自动迁移命令。v0.3.0 模块需要按 [从 v0.3.0 迁移](./migration-from-v0.3.0.md) 的清单手工重写：把旧固定导出、workflow 参数、数据契约、页面入口和环境选择器迁到 0.4.0 装饰器路径。最终 gate 只认 `manifest lock`、`check full`、`check release`、`package build`、`package verify` 和宿主联调结果；`package verify` 必须验证已经构建出的 ZIP。
