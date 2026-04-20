# 常见问题

下面每一条都按“症状 -> 怎么确认 -> 怎么修”写。

## 最短排障分叉

如果你一时间不知道该看哪条 FAQ，先按这个顺序缩小范围:

1. 没有 `🐞 调试` 按钮:
   先查是不是 DevLink 模块
2. 有按钮但没有任务实例:
   先查作业运行模板是不是绑定了正确模块和 workflow
3. 有任务实例但没有你要的日志:
   先在 task / workflow 里补 `ctx.logger.info(...)`
4. 数据表入口有了但空白:
   先查 `declare_ui`
5. 按钮有了但 handler 不触发:
   先查 handler 名和签名

## 最小观察手法

不会调试时，先别急着猜 `ctx.runtime` 或 `ctx.get_config()`，直接打日志:

```python
ctx.logger.info(
    "debug snapshot workflow=%s devel_mode=%s city=%s",
    ctx.runtime.get("workflow"),
    ctx.runtime.get("devel_mode"),
    ctx.get_config("city"),
)
```

然后去两个地方看:

1. `📋 任务监控` -> 作业详情 -> `任务日志`
2. `📊 仪表盘` -> `系统实时日志`

## `uv run crawler4j check <level>` 不通过

最常见原因:

- `module.yaml.name` 不合法
- `upgrade_source.repo` 不是 `owner/repo`
- `workflows` 为空
- 还残留 `sdk_version_range`
- `ui_extension.entry` 或 `detail_menu.entry` 格式不对

直接确认:

```bash
uv run crawler4j check full
```

修法:

- 对照错误逐项改 `module.yaml`
- 不要边跳过错误边继续写业务代码

## 明明在模块里，CLI 却说找不到 `module.yaml`

症状:

- `crawler4j task create ...`
- `crawler4j workflow create ...`
- `crawler4j check full`

直接失败，说当前目录不在 model 项目中。

直接确认:

```bash
pwd
test -f module.yaml && echo ok || echo bad
```

修法:

- 先切回模块根目录再执行
- 不要长期依赖 CLI 向上回溯找根目录

## workflow 跑不到你以为的流程

直接确认:

1. 看运行模板里选的 workflow 是不是目标 workflow
2. 看 `ctx.runtime["workflow"]` 是什么
3. 看 `module.yaml.workflows` 里有没有这个名字
4. 看 `module_runtime.py` 是否覆盖了默认 workflow

修法:

- 先把作业运行模板选对
- 再确保 workflow 名和清单一致

## 固定环境池作业没有进入等待队列

最常见原因不是 helper 没生效，而是运行模板根本没走固定池契约。

直接确认:

1. 作业类型是不是 `Service Job`
2. 运行模板是不是 `选择环境`
3. `resource_pool` 有没有填稳定池名
4. 是不是只有 `selector_name`、没有 `resource_pool`
5. 作业摘要里是不是已经显示 `资源池: <pool>`

修法:

- 要进入等待队列，必须是 `Service Job + select + resource_pool`
- 只有 `selector_name` 的旧模式里，`select_env(...)` 返回 `None` 会直接失败
- `selector_name` 留空并不是报错；宿主会直接选当前池里的第一个可分配候选
- 如果你保留 selector，真正要检查的是 `module_runtime.py` 里通过 `@env_selector(...)` 声明的函数，而不是去找一个名叫 `select_env` 的自定义 hook

## `replace_resource_pool_snapshot(...)` 一调用，整个池像被清空了

高概率是把它当成增量 patch 了。

直接确认:

1. 这次传的 `entries` 是不是这个池当前完整权威列表
2. 你是不是只传了“这次变更的几个 env”
3. 清空后任务是不是开始大量出现 `等待环境池工位: <pool>`

修法:

- 把 `replace_resource_pool_snapshot(...)` 当成整池重建，不要当 patch
- 未出现在 `entries` 里的环境卡片会被删除
- 只想临时停发号时，改用 `mark_resource_pool_ineligible(...)`

## 资源池 helper 报 `env_id is required`

这通常不是 helper 坏了，而是调用时当前 `TaskContext` 根本没有绑定环境。

直接确认:

1. 你是不是在没有环境上下文的批量扫描、宿主启动恢复或离线对账逻辑里调用 helper
2. 这次调用有没有显式传 `env_id`
3. 你传的是不是宿主 `environments.id`，而不是外部 `browser_id` / `external_id` 或业务账号 ID
4. 如果是全量重建，你是不是本来就该用 `replace_resource_pool_snapshot(...)`

修法:

- 当前上下文已绑定环境时再省略 `env_id`
- 没有环境上下文时显式传 `env_id`
- `prepare_env` 阶段不要写资源池卡片；那时 `TaskContext.env_id` 当前还是 `0`
- 批量对账优先直接提交整池权威快照

## `ctx.page` 是 `None`

这通常不是 task 写错了，而是当前运行环境没有可用页面。

修法:

```python
if ctx.page is None:
    return TaskResult.fail(message="当前环境没有可用页面", error="page_unavailable")
```

不要假装继续执行。

## 配置为什么读不到

最常见错误是读错地方。

正确边界:

- 持久配置 -> `ctx.get_config()` / `ctx.config`
- 运行模板和一次性参数 -> `ctx.runtime["params"]`
- 当前 workflow 名 -> `ctx.runtime["workflow"]`

修法:

- 配置问题先查 `ctx.get_config`
- 一次性参数先查 `ctx.runtime`
- 不要混用

## 数据表入口有了，但页面是空的

直接确认顺序:

1. `module.yaml.ui_extension.detail_menu` 里是否有 `core:data_table:<view_id>`
2. `module_runtime.py` 里是否存在 `declare_ui`
3. 根 `__init__.py` 是否仍是 SDK 托管薄壳，没有被手工改坏
4. `declare_ui` 是否是同步函数
5. schema 的 `dataset` 是否与 `view_id` 一致
6. schema 是否含不支持字段

修法:

- 先修入口和 `module_runtime.py`
- 再确认根薄壳还在自动透传 `module_runtime.py`
- 再修 schema
- 最后刷新页面，不要一上来怀疑 UI 缓存

## `create_handler` / `update_handler` 没触发

直接确认:

1. schema 里是否声明了 `create_handler` / `update_handler`
2. `module_runtime.py` 里是否存在这些函数
3. 根 `__init__.py` 是否仍保留 SDK 托管的 `__getattr__`
4. 这些函数是否为同步函数
5. handler 名字是否和 schema 字符串完全一致

修法:

- 名字对齐
- 同步函数
- 保持标准根薄壳不被破坏

这三件事缺任何一件都不会通。

## 数据更新一半，另一半丢了

高概率是误用了 `db.replace_records`。

直接确认:

- 你的写法是不是“读旧列表 -> 改一部分 -> 全量覆盖”
- 有没有两个 task 同时写同一个 dataset

修法:

- 明白 `db.replace_records` 是全量覆盖，不是 patch
- 有并发写时先加锁
- 如果写逻辑越来越复杂，回头重做数据集设计

## 结果看起来像旧代码

如果你是 DevLink 模块，先确认:

1. 模块详情页来源是不是 `开发链接`
2. 执行时 `ctx.runtime["devel_mode"]` 是否为 `True`
3. 你改的是不是实际被执行的 workflow / task

修法:

- 先确认来源，再确认运行模板，再确认代码路径
- 不要一边猜缓存，一边继续堆抽象

## `🐞 调试` 按钮不出现

直接确认:

1. 模块详情页来源是不是 `开发链接`
2. 目标作业绑定的是不是这个 DevLink 模块

修法:

- 先到 `📦 模块管理` 重新挂 DevLink
- 再回 `📋 任务监控` 检查作业运行模板

## 等待确认直接报错

高概率是给 `TaskSignal.wait_for_confirmation(...)` 传了错误的 `env_action`。

当前正确语义:

- 只允许 `KEEP_ALIVE` 或默认值

修法:

- 改成 `EnvAction.KEEP_ALIVE`
- 不要给它传 `DESTROY` / `RECYCLE`

## 调试对话框提示 `debugpy is not installed`

症状:

- 任务调试窗口的 `最近错误` 出现 `debugpy is not installed`

修法:

- 给宿主调试 worker 所在运行环境安装 `debugpy`
- 安装后重新打开 `🐞 调试`

## 正式安装失败

最常见原因:

- ZIP 里不是单一根目录
- 根目录缺 `module.yaml`
- `upgrade_source.repo` 不合法

直接确认:

```bash
unzip -l <module>.zip | sed -n '1,40p'
```

修法:

- 重新按单根目录打包
- 确保 `<module_name>/module.yaml` 在 ZIP 内顶层可见

## 正式安装后行为还像本地源码

直接确认:

1. 模块来源是不是仍然是 `开发链接`
2. 同名 DevLink 是否已被正式安装移除
3. 你是不是拿 wheel 当正式安装包用了

修法:

- 正式安装只认 ZIP
- 安装成功后去模块详情页确认来源已经不是 DevLink
