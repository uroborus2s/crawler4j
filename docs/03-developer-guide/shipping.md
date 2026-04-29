# 交付模块

模块正式交付物仍然是 ZIP 升级包，但协议已经切到 `core-native-v1`。

交付链路里有 4 个对象：

| 对象 | 作用 | 入口 |
|---|---|---|
| 模块源码 | 业务代码与 `module.yaml` | 模块项目本身 |
| 模块 ZIP | 宿主可安装的正式产物 | `uv run crawler4j package build` |
| GitHub Release | ZIP 的远端分发面 | `uv run crawler4j release ...` |
| 宿主安装/升级 | 把 ZIP 真正装进宿主 | `host install ...` / `host upgrade ...` |

DevLink 只服务开发联调，不属于正式交付。

## 发布前提

至少先过这两层：

```bash
uv run crawler4j check release
uv run crawler4j check full
```

这里会确认：

- `module.yaml.runtime_api == core-native-v1`
- `default_workflow` 与工作流声明一致
- 页面导航、页面文件、handler 能对齐
- legacy 结构没有混进来

## 构建 ZIP

```bash
uv run crawler4j package build
uv run crawler4j package verify dist/<module>-<version>.zip
```

默认产物：

```text
dist/<module>-<version>.zip
```

## ZIP 结构要求

宿主安装器只接受单根目录 ZIP。最小结构通常类似：

```text
hotel_demo/
  module.yaml
  __init__.py
  pyproject.toml
  tasks/
  workflows/
  hooks/
  env_selectors/
  pages/
```

关键约束：

- ZIP 里只能有一个根目录
- 根目录下必须有 `module.yaml`
- `module.yaml.runtime_api` 必须是 `core-native-v1`
- `module.yaml.upgrade_source.repo` 必须是合法 `owner/repo`

下面这些会被视为错误交付物：

- 缺少 `tasks/` 或 `workflows/`
- 仍然依赖根包运行入口
- 运行时代码 import `crawler4j-sdk`
- 混入 `ui/`、`config_schema.json`、`strategy.yaml` 等旧结构

## 宿主安装与升级

本地验收或首次安装：

```bash
uv run crawler4j host install preview dist/<module>-<version>.zip --skip-remote-check
uv run crawler4j host install apply dist/<module>-<version>.zip --skip-remote-check
```

正式发布后：

```bash
uv run crawler4j release status
uv run crawler4j release publish --dry-run
uv run crawler4j release publish
uv run crawler4j host upgrade check <module_name>
uv run crawler4j host upgrade preview <module_name>
uv run crawler4j host upgrade apply <module_name>
```

## GitHub Release 边界

Release 只负责远端分发 ZIP，不负责安装。

正式约束：

- 每个可安装 Release 只能提供唯一 ZIP 资产
- ZIP 内 `module.yaml.version` 必须与目标 Release 版本一致
- ZIP 内 `module.yaml.upgrade_source.repo` 必须与目标仓库一致

## 运行时依赖口径

交付给宿主的模块运行时代码只依赖 `crawler4j-contracts`。这意味着：

- 模块自己的 `pyproject.toml` 运行时依赖应只有 contracts
- `crawler4j-sdk` 只应存在于开发依赖
- 在模块运行环境里卸载 `crawler4j-sdk` 后，模块仍必须可运行

## 验收口径

完成交付至少要看到这些事实：

1. `check release` 和 `check full` 通过
2. `package verify` 通过
3. 宿主能成功安装 ZIP
4. 模块详情页来源不再是 `开发链接`
5. 宿主不调用模块根入口，也能执行任务、工作流、Hook、环境选择器和页面
6. 旧模块没有迁移时，宿主会直接报明确错误，而不是做兼容桥
