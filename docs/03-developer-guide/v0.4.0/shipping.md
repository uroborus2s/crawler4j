# 交付模块

> 版本绑定：本文只适用于 0.4.x SDK / Contracts 与 Core 0.4.0。0.4.x ZIP 包不需要兼容 0.3.x 宿主安装链或旧模块结构。

0.4.0 模块交付物仍是 ZIP。差异在发布前质量门：

- 必须通过装饰器扫描
- 必须生成 manifest lock
- 必须阻断 workflow 普通参数
- 必须阻断宿主保留数据字段

DevLink 只服务开发联调，不是正式交付。

## 发布前检查

```bash
uv run crawler4j check structure
uv run crawler4j manifest lock
uv run crawler4j check full
uv run crawler4j check release
```

这里至少确认：

- `module.yaml.runtime_api == core-native-v2`
- 装饰器名称唯一
- 对象图无环
- workflow 不声明 parameters
- component 参数合法
- page action 纯函数约束通过
- 数据表、索引、查询输出不使用宿主保留字段
- manifest lock 与源码一致
- 运行时代码没有依赖 `crawler4j-sdk`

`package build` 会先执行 full gate 再刷新 lock；因为 full gate 要求已有 lock 且未过期，发布前必须先运行 `manifest lock`。

源码目录里的 `.venv/`、`dist/`、`build/`、`.git/`、缓存目录和 `*.egg-info/` 不进入 manifest lock 或 ZIP 文件集合。这些忽略目录内的 symlink 不会阻断打包；模块源码、数据、页面、工作流等实际交付文件里的 symlink 仍会被拒绝。`package verify` 对正式 ZIP 包的安全策略不变：ZIP 内 symlink 和路径穿越仍然失败。

## 构建 ZIP

```bash
uv run crawler4j package build
uv run crawler4j package verify dist/<module>-<version>.zip
```

默认产物：

```text
dist/<module>-<version>.zip
```

## ZIP 结构

最小结构：

```text
hotel_demo/
  module.yaml
  __init__.py
  pyproject.toml
  .crawler4j/
    manifest.lock.json
  interfaces/
  objects/
  workflows/
  tasks/
  data/
  pages/
  candidates/
  cleanups/
```

关键约束：

- ZIP 只有一个根目录
- 根目录下有 `module.yaml`
- `runtime_api` 是 `core-native-v2`
- `.crawler4j/manifest.lock.json` 存在且未过期
- `candidates/` 存在；它是结构校验要求目录
- `cleanups/` 存在；它是标准扫描目录，建议随模块骨架保留
- `module.yaml.upgrade_source.repo` 是合法 `owner/repo`
- 运行时代码只依赖 `crawler4j-contracts`

## 宿主安装与升级

本地验收：

```bash
# Shell B: crawler4j 宿主源码仓或已安装宿主环境
cd /absolute/path/to/crawler4j-host
uv run crawler4j host install preview /absolute/path/to/module/dist/<module>-<version>.zip --skip-remote-check
uv run crawler4j host install apply /absolute/path/to/module/dist/<module>-<version>.zip --skip-remote-check
```

这里安装的是 ZIP，不是 DevLink 源码目录。先在模块根完成 `package build` 和 `package verify`，再把 ZIP 的绝对路径交给宿主安装命令。

正式发布：

```bash
uv run crawler4j release status
uv run crawler4j release publish --dry-run
uv run crawler4j release publish
uv run crawler4j host upgrade check <module_name>
uv run crawler4j host upgrade preview <module_name>
uv run crawler4j host upgrade apply <module_name>
```

## Release 边界

GitHub Release 只负责分发 ZIP，不负责安装。

约束：

- 每个可安装 Release 只提供一个 ZIP 资产
- ZIP 内 `module.yaml.version` 与 Release 版本一致
- ZIP 内 `upgrade_source.repo` 与目标仓库一致

## 运行时依赖

运行时代码只依赖 `crawler4j-contracts`。

允许：

```python
from crawler4j_contracts import component, workflow, page_action
```

禁止：

```python
from crawler4j_sdk import ...
```

`crawler4j-sdk` 可以出现在开发依赖中，不能成为模块运行条件。

## 验收口径

完成交付至少看到这些事实：

1. `check full` 通过
2. `manifest lock` 已生成且未过期
3. `check release` 通过
4. `package verify` 通过
5. 宿主能安装 ZIP
6. 模块详情页来源不是 `开发链接`
7. 运行模板能展示对象装配树
8. 任务执行时每个 task/env 都创建独立对象实例
9. 数据表和只读视图通过 `ctx.db` 可访问
