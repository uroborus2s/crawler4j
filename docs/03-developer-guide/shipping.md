# 交付模块

模块的正式交付链路不是 DevLink，而是 ZIP 安装包。

这一页只回答三件事:

1. 正式模块应该怎么交付
2. 安装前应该自检什么
3. 什么才算真正验收通过

## 为什么正式交付是 ZIP

当前宿主正式安装链路以 ZIP 为准，不以 wheel 为准。

也就是说:

- 能 `uv build` 出 wheel，不代表宿主安装链已经打通
- 正式模块交付始终准备 ZIP 安装包

## 安装器要求的 ZIP 结构

当前安装器要求:

- ZIP 内只能有一个根目录
- 根目录下必须有 `module.yaml`
- `module.yaml` 必须声明合法的 `upgrade_source.repo`

最关键的一句:

- 压缩包展开后第一层就应该看到 `<module_name>/module.yaml`

错误示例:

- ZIP 里直接散落 `module.yaml`、`tasks/`、`workflows/`
- ZIP 里是两层根目录，比如 `dist/hotel_demo/module.yaml`
- ZIP 根目录里混入 `.venv/`、日志、缓存

## 从源码到 ZIP 的最短路径

如果你是第一次交付模块，就按这个顺序做:

1. 站在模块根目录跑 `uv run crawler4j check release`
2. 人工确认 `module.yaml`、`__init__.py`、`module_runtime.py`、`tasks/`、`workflows/` 都在
3. 直接跑 `uv run crawler4j package build`
4. 跑 `uv run crawler4j package verify dist/<module>-<version>.zip`
5. 用 `unzip -l` 做人工抽查
6. 到宿主 `📦 模块管理` 用 `📥 安装模块` 安装本地 ZIP
7. 安装完成后回到模块详情页看来源和版本

最小可交付目录应该长这样:

```text
hotel_demo/
  module.yaml
  __init__.py
  module_runtime.py
  tasks/
  workflows/
  tests/       # 可选: 有模块自测时带上
  utils/       # 可选: 有纯函数工具时再带
```

## 打包前最小自检

站在模块根目录执行:

```bash
pwd
test -f module.yaml && echo "ok: module root" || echo "not module root"
uv run crawler4j check release
```

人工再确认 4 件事:

- `module.yaml.name` 正确
- `module.yaml.upgrade_source.repo` 正确
- 目标 workflow 已声明
- `ui_extension.pages` 与 `declare_ui()` 一致

## 推荐打包命令

假设:

- 模块目录名是 `hotel_demo`
- `module.yaml.version` 当前是 `0.1.0`
- 你现在站在 `hotel_demo/` 目录里

优先用 CLI 打包:

```bash
uv run crawler4j package build
```

推荐产物命名:

```text
<module_name>-<version>.zip
```

例如:

```text
dist/hotel_demo-0.1.0.zip
```

## 打包后怎么验包

### 0. 先走 CLI 校验

```bash
uv run crawler4j package verify dist/hotel_demo-0.1.0.zip
```

期望现象:

- CLI 直接通过
- 没有单根目录、`module.yaml`、`upgrade_source.repo` 之类的错误

### 1. 看根目录

```bash
unzip -l dist/hotel_demo-0.1.0.zip | sed -n '1,40p'
```

期望现象:

- 所有条目都以 `hotel_demo/` 开头
- 很靠前的位置就能看到 `hotel_demo/module.yaml`

### 2. 看关键文件是否都在

至少应包含:

- `hotel_demo/module.yaml`
- `hotel_demo/__init__.py`
- `hotel_demo/module_runtime.py`
- `hotel_demo/tasks/`
- `hotel_demo/workflows/`

### 3. 看脏东西有没有被带进去

不应该出现:

- `.venv/`
- `.pytest_cache/`
- `.mypy_cache/`
- `.idea/`
- `.vscode/`
- 临时截图、日志、调试输出

## 在宿主里安装本地 ZIP

这里有两条路径，二选一，不要连着做:

### 路径 A: 直接用 CLI 桥接宿主安装

```bash
uv run crawler4j host install preview dist/hotel_demo-0.1.0.zip
uv run crawler4j host install apply dist/hotel_demo-0.1.0.zip
```

补两条最容易踩的规则:

- `preview` 只预检，不安装
- `apply` 才会真正安装到宿主

如果你只是本地先验包，还没准备好远端仓库可达性，可以临时加:

```bash
uv run crawler4j host install preview dist/hotel_demo-0.1.0.zip --skip-remote-check
```

### 路径 B: 在宿主 UI 手工安装

如果你不用 CLI 桥接安装，就在宿主里按这个路径点:

1. 左侧导航进入 `📦 模块管理`
2. 点击 `📥 安装模块`
3. 选择 `本地 ZIP`
4. 点击 `浏览…`
5. 选中你的 ZIP
6. 点击 `开始检查`
7. 在预览弹窗确认后点击安装

安装完成后，去模块详情页核对:

- `来源` 不应再是 `开发链接`
- 版本、路径、详情菜单都正常

## 最小验收清单

### 结构与契约验收

| 输入 | 动作 | 期望结果 |
|---|---|---|
| 站在模块根目录 | `test -f module.yaml && test -f __init__.py && test -f module_runtime.py` | 三个关键文件都存在 |
| 站在模块根目录 | `uv run crawler4j check release` | 退出码为 `0`，无错误输出 |
| 打开 `module.yaml` | 检查 `name`、`upgrade_source.repo`、`workflows` | `name` 合法，`repo` 为 `owner/repo`，`workflows` 非空 |
| 打开 `module.yaml` | 检查 `ui_extension.pages` | 页面入口只允许 `core:page:<id>` 或 `core:data_table:<id>` |
| 检查清单文件 | `rg -n "sdk_version_range" module.yaml` | 无结果 |
| 检查模块根目录 | `test ! -f config_schema.json && test ! -f strategy.yaml` | 两个旧配置文件都不存在 |

### 开发态冒烟，不等于正式交付

这一组只用来验证你的 workflow 和日志链路还活着，不算正式 ZIP 交付验收。

| 输入 | 动作 | 期望结果 |
|---|---|---|
| DevLink 模块已挂载 | 在 `📋 任务监控` 创建作业并点 `▶ 执行一次` | 作业能真正启动，不是空跑 |
| 有最小 workflow | 执行一次后打开作业详情 | `任务实例 (Tasks)` 里能看到 task 记录 |
| workflow/task 已打阶段日志 | 查看作业详情下方 `任务日志` | 能看到关键阶段日志，例如登录、抓取、保存 |
| 模块会返回结构化结果 | 检查 task 最终状态和结果消息 | `TaskResult` 的 `message`、`error`、`signal` 与预期一致 |
| 模块依赖页面环境 | 在可用页面环境下执行 | `ctx.page` 不为空时逻辑正常；无页面时明确失败而不是假装继续 |

### 正式 ZIP 安装后的运行验收

这一组才是“正式交付真的通了”的判据:

| 输入 | 动作 | 期望结果 |
|---|---|---|
| 已完成 ZIP 安装 | 打开模块详情页 | 来源不再是 `开发链接` |
| 已完成 ZIP 安装 | 在 `📋 任务监控` 新建或切到绑定该正式模块的作业 | 运行模板能选到已安装模块 |
| 已安装模块已有最小 workflow | 点 `▶ 执行一次` | 作业真正启动 |
| 执行完成后查看作业详情 | 查看 `任务实例 (Tasks)` 与 `任务日志` | 正式安装模块也能留下正确日志与结果 |

### 抽象边界验收

| 输入 | 动作 | 期望结果 |
|---|---|---|
| 查看模块代码目录 | `rg --files tasks workflows ui utils | rg '/(services|repositories|controllers|stores?)/'` | 通常无结果 |
| 全局检索核心代码 | `rg -n "BaseTask|BaseWorkflow|ContextFacade|DbClient|CoreApi|HostRuntimeAdapter" __init__.py module_runtime.py tasks workflows ui utils` | 通常无结果 |
| 阅读 `module_runtime.py` | 观察职责 | 只做薄扩展、生命周期 hook、轻量同步 UI handler |
| 阅读 workflow | 观察职责 | 只做编排，不塞重页面操作和数据持久化细节 |
| 阅读 task | 观察职责 | 一个 task 只做一个原子业务动作 |

### ZIP 与正式安装验收

| 输入 | 动作 | 期望结果 |
|---|---|---|
| 已产出 ZIP | `uv run crawler4j package verify dist/<module>-<version>.zip` | CLI 校验通过，无结构错误 |
| 已产出 ZIP | `unzip -l <module>.zip | sed -n '1,40p'` | 所有条目都在单一根目录下，且存在 `<module>/module.yaml` |
| 已产出 ZIP | 检查压缩内容 | 不包含 `.venv/`、缓存、IDE 配置、日志、截图 |
| 在宿主里选择 `📥 安装模块` | 安装本地 ZIP | 安装成功，无结构或升级源错误 |
| 安装完成后打开模块详情页 | 检查模块来源 | 来源不再是 `开发链接` |
| 同名模块先前存在 DevLink | 安装正式 ZIP 后再看详情页 | 不再依赖本地 DevLink 目录 |

## GitHub Release 约束

如果走 GitHub Release 安装，当前约束是:

- 仓库必须可访问
- 每个可安装版本必须且只能上传一个 `.zip` 模块安装包

## DevLink 和正式安装的边界

- DevLink 只用于联调
- 正式安装用 ZIP
- 同名正式安装会移除同名 DevLink

所以不要用“我本地 DevLink 能跑”代替正式安装验收。
