# 交付模块

模块的正式交付物是 ZIP 升级包。GitHub Release 是升级包的远端分发面，`host install` 和 `host upgrade` 是宿主消费升级包的入口。DevLink 只服务开发调试，不属于正式交付链路。

## 先分清四个对象

| 对象 | 负责什么 | 对应入口 |
|---|---|---|
| 模块源码 | 业务逻辑、`module.yaml`、`module_runtime.py`、workflow、UI 声明 | 模块项目本身 |
| 模块升级包 | 宿主可安装的正式单根目录 ZIP | `uv run crawler4j package build` |
| GitHub Release | ZIP 升级包的远端版本分发面 | `uv run crawler4j release ...` |
| 宿主安装与宿主升级 | 把 ZIP 或 Release 资产真正落到宿主 | `uv run crawler4j host install ...` / `host upgrade ...` |

边界要点：

- `package` / `release` 面向升级包和分发，不修改宿主安装状态
- `host install` / `host upgrade` 面向宿主，不负责打包
- DevLink 不是交付方式，wheel 也不是宿主正式模块安装格式

## 正式交付主线

### 1. 先过发布前提

```bash
uv run crawler4j check release
```

这一层负责确认：

- 模块结构完整
- `module.yaml.version` 合法
- `module.yaml.upgrade_source.repo` 合法
- `config_defaults`、workflow、UI 入口满足发布要求

### 2. 构建模块升级包

```bash
uv run crawler4j package build
```

默认产物：

```text
dist/<module>-<version>.zip
```

这一步产出的 ZIP 就是模块升级包。后续无论走本地安装、GitHub Release，还是宿主升级，消费的都是这个资产。

### 3. 校验升级包

```bash
uv run crawler4j package verify dist/<module>-<version>.zip
```

必要时再做人工抽查：

```bash
unzip -l dist/<module>-<version>.zip | sed -n '1,40p'
```

### 4. 选择分发方式

本地验收或首次安装：

```bash
uv run crawler4j host install preview dist/<module>-<version>.zip
uv run crawler4j host install apply dist/<module>-<version>.zip
```

远端版本分发：

```bash
uv run crawler4j release status
uv run crawler4j release publish --dry-run
uv run crawler4j release publish
```

正式安装后的升级验收：

```bash
uv run crawler4j host upgrade check <module_name>
uv run crawler4j host upgrade preview <module_name>
uv run crawler4j host upgrade apply <module_name>
```

## 模块升级包要求

宿主安装器只认单根目录 ZIP。正式约束如下：

- ZIP 内只能有一个根目录
- 根目录下必须有 `module.yaml`
- `module.yaml.upgrade_source.repo` 必须是合法的 `owner/repo`
- 压缩包第一层就应该能看到 `<module_name>/module.yaml`

错误示例：

- ZIP 根目录直接散落 `module.yaml`、`tasks/`、`workflows/`
- ZIP 里出现两层根目录，例如 `dist/hotel_demo/module.yaml`
- ZIP 里混入 `.venv/`、缓存、日志、截图、IDE 配置

最小可交付目录通常应类似：

```text
hotel_demo/
  module.yaml
  __init__.py
  module_runtime.py
  tasks/
  workflows/
```

## GitHub Release 的责任边界

GitHub Release 在这条链路里只负责“让宿主能找到远端升级包”。

正式约束：

- 仓库必须可访问
- 每个可安装 Release 必须且只能有一个 ZIP 升级包
- ZIP 内 `module.yaml.version` 必须与目标 Release 版本一致
- ZIP 内 `module.yaml.upgrade_source.repo` 必须与目标仓库一致
- `release publish` 上传的是模块升级包资产，不是源码目录

`uv run crawler4j release check-remote` 用于对比本地版本和远端最新 Release 版本；它不安装，也不修改宿主状态。

## 宿主安装入口

`host install` 是宿主消费升级包的安装入口，分 `preview` 和 `apply` 两步：

- `preview`：只预检，不安装
- `apply`：真正安装到宿主

它只接受两类来源：

- 本地 ZIP 路径
- GitHub 来源：`owner/repo`、完整仓库 URL，或完整 GitHub Release URL

它不接受源码目录。源码目录要走：

```bash
uv run crawler4j host devlink add /abs/path/to/module
```

如果你只是本地先验包，还没准备好远端仓库校验，可以在本地 ZIP 场景下使用：

```bash
uv run crawler4j host install preview dist/<module>-<version>.zip --skip-remote-check
uv run crawler4j host install apply dist/<module>-<version>.zip --skip-remote-check
```

注意：

- `--skip-remote-check` 只适用于本地 ZIP 的 `preview` / `apply`
- `module.yaml.upgrade_source.repo` 里正式写法仍必须是 `owner/repo`

## 宿主升级入口

`host upgrade` 是正式安装模块的升级入口，也分 `check`、`preview`、`apply` 三步：

- `check`：看当前安装版本和远端最新版本
- `preview`：下载并预览升级包，但不安装
- `apply`：下载并安装升级包

它的前提是：

1. 模块已经处于正式安装态
2. 模块声明了可访问的 `upgrade_source.repo`
3. GitHub Release 上存在满足约束的唯一 ZIP 资产

还要补一条运行态约束：

- `check` 只检查版本与远端可用性
- `preview` 和 `apply` 都要求模块当前没有运行中任务；模块不空闲时，宿主会拒绝升级

这条入口不服务 DevLink 模块，也不消费源码目录。

## DevLink 与正式安装的边界

- DevLink：源码联调
- ZIP：正式交付物
- GitHub Release：ZIP 的远端分发面
- `host install`：首次安装、本地验收、从仓库直接安装
- `host upgrade`：已安装模块的后续升级

同名正式安装成功后，宿主会切换到正式模块来源，不再继续依赖本地 DevLink 目录。

## 最小验收口径

一份模块交付完成，至少要看到下面这些事实：

1. `check release` 通过
2. `package verify` 通过
3. 宿主能成功安装 ZIP，或能从 GitHub 仓库 / Release URL 直接安装
4. 模块详情页来源不再是 `开发链接`
5. 宿主里能选到该模块并执行最小 workflow
6. Hosted UI 页面都能正常打开，内联 `DataTable` 的搜索、排序、分页与跳转行为符合预期

如果你还要验证正式升级，再补两步：

1. `host upgrade check` 能看到新版本
2. `host upgrade apply` 后版本和行为都更新到新 Release
