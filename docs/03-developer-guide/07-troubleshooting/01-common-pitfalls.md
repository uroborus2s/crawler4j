# 7.1 常见问题与坑位

## 1. `uv run crawler4j ...` 找不到命令

最常见原因是你在模块目录里还没有执行：

```bash
uv sync
```

如果你是刚用 `--no-install` 创建的模块项目，这个问题尤其常见。

### 先检查什么

1. 你是不是已经进入模块根目录
2. 模块项目里是不是执行过 `uv sync`
3. 当前 Python 环境是不是确实由 `uv run` 启动

## 2. CLI 提示当前目录不在 model 项目中

说明当前目录或父目录找不到 `module.yaml`。  
不要继续排别的问题，先确认你已经进入模块根目录。

### 小白最容易做错的目录

常见误入目录包括：

- 模块父目录
- `tasks/`
- `workflows/`

这些目录都可能让你误以为“我明明就在项目里”，但 CLI 看的其实是最近一层的 `module.yaml`。

## 3. 模块在自己项目里能 import，放进宿主就依赖缺失

这是当前真实限制：宿主不会自动安装模块项目自己的第三方依赖。  
你需要确认宿主环境里同样具备这些依赖。

### 怎么快速判断是不是这个问题

如果你的现象是：

- 模块项目里运行正常
- 宿主里一执行就 `ModuleNotFoundError`

那大概率就是这个问题，而不是你的业务逻辑突然失效。

## 4. 我已经注册了模块，为什么 ATM 里没有 `🐞 调试`

按下面顺序排查：

1. 模块来源是不是 `DevLink`
2. 作业是不是已经保存运行模板
3. `execution.module` 是不是 `module.yaml.name`
4. 你是不是刚安装了同名 zip，导致 DevLink 被移除

### 排查时先不要做什么

先不要急着改 IDE 配置。如果入口按钮都没出现，问题通常还没到 IDE 这一步。

## 5. 我写了工作流文件，但运行配置里选不到

常见原因有两个：

1. 你只创建了 Python 文件，没有同步写入 `module.yaml.workflows`
2. 工作流名字和运行配置里的 `execution.workflow` 不一致

### 最稳的避免方式

第一次开发模块时，优先使用：

```bash
uv run crawler4j add-workflow <workflow_name>
```

它会同时帮你补文件和更新清单。

## 6. zip 安装失败

最常见的结构问题只有两类：

1. zip 中有多个根目录
2. 根目录里缺少 `module.yaml`

第一次打包时，尽量在模块父目录执行：

```bash
uv run python -m zipfile -c hotel_demo-1.0.0.zip hotel_demo
```

### 安装失败时最值钱的动作

先解压 zip 看结构，而不是先怀疑宿主。对新手来说，这通常是定位最快的一步。

## 7. 我已经安装了 zip，为什么还是在跑本地源码

先回模块管理页看来源。  
当前设计下，同名正式安装通常会清掉 DevLink；如果你仍然看到源码行为，优先确认是否刷新了模块列表，以及当前任务运行配置最终解析到的模块来源是什么。

### 一个常见误会

很多人会把“我改了源码，行为还在变”误判成“宿主还在跑 DevLink”。实际上也可能是你并没有确认当前运行配置最终指向哪个来源，所以还是要回来源和任务配置上核对。

## 8. 我写了代码型 UI 页面，但应用里只看到降级页

说明你命中了 trust gate 或页面加载条件不满足。  
重点检查：

1. `ui_extension.type` 是否为 `micro_app`
2. `detail_menu.entry` 是否写成 `ui:YourWidget`
3. 模块里是否存在 `ui.py`
4. `ui.py` 是否导出了对应的 `QWidget` 类
5. 模块来源是否为 `DevLink` / 内置，或是否已命中 `mms.ui.allowlist`

### 对小白的建议

如果你现在连任务脚本、工作流、调试和 zip 安装都还没完全跑通，先不要优先处理这个问题。先把模块主链做稳，再回头处理代码型 UI，效率会更高。

## 9. `ctx.run_subtask()` 返回值跟预期不一样

当前返回值并不总是完整 `TaskResult`。  
如果子任务返回了 `TaskResult.ok(data=...)`，你更可能直接拿到的是 `data`。  
所以工作流里要按“拿到的是数据或布尔值”来写，不要默认它一定是完整结果对象。

### 一个最稳的写法思路

- 需要数据，就让子任务返回 `data`
- 只关心成功失败，就按真假值判断

不要默认写成 `result.success`。

## 10. 看起来哪里都对，但模块就是不运行

最后按这条最短链路做一次总复盘：

```text
module.yaml.name
-> DevLink / 正式安装来源
-> job.run_profile.execution.module
-> job.run_profile.execution.workflow
-> 作业保存运行模板
-> ATM 触发执行
```

这六个点里只要有一个不一致，运行链就会断。

## 11. 我想直接连宿主数据库，或者旧模块还在用已删除的 `DataService` 写法

先停下来。当前正式约束不是这样。

现在模块里真正稳定可用的数据接口只有 `ctx.tools.call("db.*", ...)`，而且能力面只覆盖：

1. 数据集查询
2. 数据集写入
3. 轻量状态
4. 幂等锁

如果你遇到的现象是：

- 想拿 SQLite 连接但拿不到
- 想写 `ctx.db.storage.state`
- 想用 `ctx.db.accounts` / `ctx.db.tasks`

那优先判断这是不是踩到了旧口径，而不是继续往业务代码里加私有适配。

### 正确处理方式

优先改成下面这组当前正式接口：

- `ctx.tools.call("db.list_records", ...)`
- `ctx.tools.call("db.replace_records", ...)`
- `ctx.tools.call("db.get_state", ...)`
- `ctx.tools.call("db.set_state", ...)`
- `ctx.tools.call("db.acquire_lock", ...)`

如果你在升级旧模块，再补两步：

1. 删除 `DataService` 导入和专用 `ctx.db` 依赖
2. 把 `module.yaml.sdk_version_range` 改成 `>=1.1.1`

## 最后给小白的一条建议

排错时，尽量按“从外到内”的顺序查：

1. 目录和清单对不对
2. 模块来源对不对
3. 运行模板字段对不对
4. 调试入口有没有出现
5. 最后才看具体 Python 业务逻辑

这样通常比一开始就扎进代码里更快找到问题。
