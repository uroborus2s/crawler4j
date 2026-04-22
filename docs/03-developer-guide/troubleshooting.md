# 常见问题

这一页按“运行与交付主线”排问题。先判断你卡在模块工程、DevLink/ATM、Hosted UI、ZIP 交付，还是宿主安装/升级，再看对应条目。

## 最短定位顺序

1. CLI 不通过：先看 `check`、模块根目录和 `module.yaml`
2. DevLink 不生效：先看模块来源是不是 `开发链接`
3. ATM 跑不对：先看作业绑定的模块和 workflow
4. 页面或数据表空白：先看 `declare_ui()` 和 `check full`
5. 正式安装失败：先看 ZIP 结构和 `upgrade_source.repo`
6. 升级不生效：先看模块是否处于正式安装态、远端 Release 是否存在 ZIP 资产

## `uv run crawler4j check <level>` 不通过

确认：

- 当前目录下有 `module.yaml`
- `module.yaml.version` 是合法语义化版本
- `module.yaml.upgrade_source.repo` 是合法的 `owner/repo`
- `ui_extension.pages[].entry` 只使用 `core:page:*` 或 `core:data_table:*`

处理：

- 先执行 `uv run crawler4j check full`
- 按错误逐项改 `module.yaml` 或 `module_runtime.py`
- 不要带着已知 gate 错误继续写业务代码

## 明明在模块里，CLI 却说找不到 `module.yaml`

确认：

```bash
pwd
test -f module.yaml && echo ok || echo bad
```

处理：

- 切回模块根目录再执行 CLI
- 不要长期依赖 CLI 向上回溯猜根目录

## workflow 跑不到你以为的流程

确认：

1. ATM 运行模板里选中的 workflow 是不是目标 workflow
2. `ctx.runtime["workflow"]` 是什么
3. `module.yaml.workflows` 里是否声明了该 workflow
4. `module_runtime.py` 是否改过默认 workflow

处理：

- 先修运行模板
- 再修清单和默认 workflow

## Hosted UI 页面或数据表是空白

确认：

1. `module.yaml.ui_extension.pages[]` 是否存在对应入口
2. `module_runtime.py` 是否存在同步 `declare_ui()`
3. `uv run crawler4j check full` 是否通过
4. Hosted UI 是否真的调用了 `ui.declare_page`
5. 数据表是否真的调用了 `ui.declare_data_table`

处理：

- 先修声明链，再回宿主点击 `刷新`
- 不要一上来就猜 UI 缓存

## `create_handler` / `update_handler` 没触发

确认：

1. schema 是否声明了 `create_handler` / `update_handler`
2. `module_runtime.py` 里是否存在这些函数
3. 这些函数是否为同步函数
4. handler 名字是否与 schema 字符串完全一致
5. 根 `__init__.py` 是否仍保留 SDK 托管薄壳

处理：

- 名字对齐
- 改回同步函数
- 不要改坏根薄壳

## 结果看起来像旧代码

确认：

1. 模块详情页来源是不是 `开发链接`
2. `ctx.runtime["devel_mode"]` 是否为 `True`
3. 你改的是不是 ATM 实际绑定的 workflow / task

处理：

- 先确认运行来源
- 再确认运行模板
- 最后确认代码路径

## `调试` 按钮不出现

确认：

1. 模块来源是不是 `开发链接`
2. 作业绑定的是不是这个 DevLink 模块

处理：

- 重新注册 DevLink
- 回 ATM 重新检查模块和 workflow 绑定

## 调试对话框提示 `debugpy is not installed`

确认：

- 报错发生在宿主调试会话里，而不是你的模块虚拟环境里

处理：

- 给宿主调试 worker 所在的 Python 环境安装 `debugpy`
- 安装后重新创建调试会话

## 固定环境池作业没有进入等待队列

确认：

1. 作业类型是不是 `Service Job`
2. 运行模板是不是 `选择环境`
3. `resource_pool` 有没有填写
4. 是不是只有 `selector_name`、没有 `resource_pool`
5. `task.message` 是否包含 `等待环境池工位: <pool>`

处理：

- 固定池等待必须是 `Service Job + select + resource_pool`
- 只有 `selector_name` 的旧模式里，选择器返回 `None` 会直接失败

## 资源池 helper 报 `env_id is required`

确认：

1. 当前 `TaskContext` 是否真的绑定了宿主环境
2. 你传的是不是宿主 `environments.id`，而不是外部浏览器 ID 或业务账号 ID
3. 是不是在 `prepare_env` 之类尚未拿到正式 `env_id` 的阶段调用了 helper

处理：

- 没有环境上下文时显式传 `env_id`
- `prepare_env` 阶段不要写资源池卡片
- 批量重建时优先走 `replace_resource_pool_snapshot(...)`

## 数据更新一半，另一半丢了

确认：

1. 你是不是把 `db.replace_records` 当成了增量更新
2. 有没有两个 task 同时写同一个 dataset

处理：

- 记住 `db.replace_records` 是全量覆盖
- 有并发写时先加锁
- 写逻辑越来越复杂时，回头重做数据集设计

## `ctx.page` 是 `None`

确认：

- 当前作业运行环境是否真的提供了可用页面

处理：

```python
if ctx.page is None:
    return TaskResult.fail(message="当前环境没有可用页面", error="page_unavailable")
```

不要假装继续执行。

## 配置为什么读不到

确认：

- 宿主持久配置是不是从 `ctx.get_config()` / `ctx.config` 读取
- 一次性输入是不是从 `ctx.runtime["params"]` 读取
- 当前 workflow 是不是从 `ctx.runtime["workflow"]` 读取

处理：

- 配置读 `ctx.get_config()`
- 运行态读 `ctx.runtime`
- 不要混用

## `host install` 拒绝源码目录

确认：

- 你传给 `host install preview|apply` 的是不是本地源码目录

处理：

- 源码目录走 `uv run crawler4j host devlink add <module_root>`
- `host install` 只接受 ZIP 或 GitHub 仓库 `owner/repo`

## 正式安装失败

确认：

```bash
uv run crawler4j package verify dist/<module>-<version>.zip
unzip -l dist/<module>-<version>.zip | sed -n '1,40p'
```

重点看：

- ZIP 是否是单根目录
- 根目录下是否有 `module.yaml`
- `upgrade_source.repo` 是否合法

处理：

- 重新按单根目录打包
- 确保 `<module_name>/module.yaml` 在 ZIP 内顶层可见

## 正式安装后行为还像本地源码

确认：

1. 模块详情页来源是不是仍然显示为 `开发链接`
2. 你是不是把 wheel 当成正式安装包用了
3. 正式安装后是否真的切换到了新来源

处理：

- 正式安装只认 ZIP 或 GitHub 仓库安装
- 安装完成后回模块详情页确认来源已经不是 DevLink

## `host upgrade` 看不到新版本

确认：

1. 目标模块是否已经处于正式安装态
2. `module.yaml.upgrade_source.repo` 是否正确
3. GitHub Release 上是否真的有当前版本之后的新 ZIP 资产

处理：

- 先确认该模块不是 DevLink
- 再确认远端 Release 和资产
- 必要时先执行 `uv run crawler4j release check-remote`

## `host upgrade apply` 后版本没变

确认：

1. `host upgrade preview <module_name>` 看到的远端版本是否真的是新版本
2. 模块详情页是否刷新到了新来源和新版本
3. 远端 Release 上传的是否就是目标 ZIP 升级包

处理：

- 先跑 `check` 和 `preview`
- 再执行 `apply`
- 升级后回宿主详情页重新核对版本和行为
