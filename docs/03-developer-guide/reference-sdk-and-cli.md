# SDK 与 CLI 参考

`crawler4j-sdk` 现在只面向开发阶段。

## 命令入口

- 模块项目内：`uv run crawler4j ...`
- 不安装直接用：`uvx --from crawler4j-sdk crawler4j ...`
- 在 Core 源码仓验证本地 CLI：`uv run python -m crawler4j_sdk.cli.commands ...`

## 模块工程命令

| 命令组 | 关键命令 | 主要输出 |
|---|---|---|
| `module` | `module init` `module show` `module set repo/version/default-workflow` | 模块根目录与 `module.yaml` |
| `task` | `task create` `task list` | `tasks/<name>.py` |
| `workflow` | `workflow create` `workflow list` | `workflows/<name>.py` 与 `module.yaml.workflows` |
| `page` | `page create` `page list` | `pages/<page>.py` 与 `ui_extension.pages[]` |
| `hook` | `hook create` `hook list` | `hooks/<hook>.py` |
| `env-selector` | `env-selector create` `env-selector list` | `env_selectors/<name>.py` |
| `config` | `config show` `config set ...` `config lint` | `module.yaml.config_defaults` |
| `check` | `check structure` `check release` `check full` | 本地校验 gate |
| `package` | `package build` `package verify` | ZIP 包 |
| `release` | `release status` `release check-remote` `release publish` | 发布辅助 |
| `host` | `host devlink ...` `host install ...` `host upgrade ...` `host debug config` | 宿主联调辅助 |

## `module init`

初始化后会生成：

- `runtime_api: core-native-v1`
- `default_workflow`
- contracts-only 运行时依赖
- sdk-only 开发依赖
- `tasks/`、`workflows/`、`hooks/`、`env_selectors/`、`pages/`

不会再生成：

- `module_runtime.py`
- 根包运行薄壳
- 任何兼容桥

## `check full`

当前会校验：

- `runtime_api == core-native-v1`
- 目录结构完整
- `default_workflow` 与 `module.yaml.workflows` 一致
- `TaskSpec/WorkflowSpec/EnvSelectorSpec/PageSpec` 导出存在
- 文件名与声明名一致
- 页面文件与 `ui_extension.pages[]` 一致
- 页面 `load_handler` / 内联 `query_handler` 存在且签名兼容
- legacy `ui/`、`config_schema.json`、`strategy.yaml` 已清理

## 环境选择器

当前正式写法只有一种：

```python
from crawler4j_contracts import EnvCandidate, EnvSelectorSpec, TaskContext

SELECTOR = EnvSelectorSpec(name="pick_ready")

def select(context: TaskContext, candidates: list[EnvCandidate]):
    ...
```
