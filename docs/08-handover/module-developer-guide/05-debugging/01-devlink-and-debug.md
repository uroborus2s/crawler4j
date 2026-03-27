# 5.1 DevLink 与真实调试链路

## DevLink 是什么

DevLink 是“模块名 -> 本地源码目录”的持久化映射。  
可以把它理解成：告诉宿主应用，“这个模块先不要从安装目录找，直接从我本地源码目录找”。

它的核心用途有三个：

1. 开发时不必反复打包
2. 宿主重启后映射仍然保留
3. 让 ATM 里的作业具备真实调试能力

如果你第一次听到 `DevLink`，可以先把它理解成：

> “宿主认识你的本地源码目录的一种方式。”

没有它，宿主通常只会认识正式安装目录里的模块，而不是你正在编辑的源码目录。

## 推荐注册方式

最推荐的方式是在宿主应用里操作：

1. 打开“模块管理”
2. 点击 `🔗 添加开发模块`
3. 选择包含 `module.yaml` 的模块目录
4. 确认来源显示为“开发链接”

### 这一步最容易做错什么

最常见的错误不是“按钮没点对”，而是选错目录。你应该选择的是：

- 包含 `module.yaml` 的模块根目录

而不是：

- 父目录
- 单独的 `tasks/` 目录
- 单独的 `workflows/` 目录

如果你在调试 Core 本身，也可以直接调用注册表：

```python
from src.core.mms import get_module_registry

get_module_registry().register_dev_link("/abs/path/to/hotel_demo")
```

## `🐞 调试` 什么时候会出现

当前并不是“有源码就能调试”，而是必须同时满足：

1. 作业已经绑定策略
2. 策略里有 `execution.module`
3. `execution.module` 能解析到一个有效模块
4. 该模块来源是 `DevLink`

只要最后一条不成立，`DebugService` 就会拒绝进入调试会话创建。

### 小白最容易忽略的点

很多人会觉得：

```text
我都能在模块列表里看到它了
=
它应该可以调试
```

这个推断不成立。“能看到”只说明被扫描或加载到了；“能调试”还要求它来自 `DevLink`。

## 策略里最关键的两个字段

至少要保证下面两个值正确：

- `execution.module = module.yaml.name`
- `execution.workflow = 想执行的工作流名`

如果你的模块名是 `hotel_demo`，但策略里写成了 `Hotel Demo`、目录显示名或 zip 文件名，调试目标解析会直接失败。

### 一个记忆方法

可以这样背：

- `execution.module` 看模块清单里的 `name`
- `execution.workflow` 看模块清单里的 `workflows[*].name`

不要看显示名，不要看目录展示名称。

## 当前真实调试链路

现在的调试链已经是宿主真实执行链，不是简化版模拟器：

```text
ATM 作业 / 策略
-> DebugService
-> DebugWorker
-> debugpy
-> ExecutionRunner
-> 模块 hooks / TaskFlow / TaskScript
```

这意味着以下位置都可以打断点：

- 根 `__init__.py` 里的 hooks
- `tasks/*.py`
- `workflows/*.py`

而且你拿到的是接近真实运行链的 `TaskContext`。

这也是为什么当前调试更有价值：你不是在调一个脱离宿主的简化脚本，而是在调接近正式运行的真实执行链。

## 一次完整调试的推荐步骤

1. 在模块管理中注册 DevLink
2. 确认模块来源显示为“开发链接”
3. 在策略里设置 `execution.module` 和 `execution.workflow`
4. 创建或选择绑定该策略的作业
5. 在 ATM 中点击 `🐞 调试`
6. 生成调试配置并让 IDE 附加到 `debugpy`
7. 从断点观察 `ctx.config`、`ctx.state`、`ctx.page`

### 第一次调试时建议重点看什么

第一次不要一上来就追所有变量。先看下面 4 个点就够了：

1. 断点有没有被命中
2. `ctx.config` 里是不是你期望的参数
3. `ctx.state` 是不是按你的流程在变化
4. `ctx.page` 是否存在、是否已经处于你期望的页面状态

这 4 个点能帮你快速判断：

- 问题是在策略参数
- 还是在工作流状态
- 还是在页面执行环境

## 为什么我看不到 `🐞 调试`

最常见的原因有四类：

1. 模块没有注册成 `DevLink`
2. 作业没有绑定策略
3. `execution.module` 不是 `module.yaml.name`
4. 你装了同名 zip，DevLink 已被正式安装替换

排查顺序建议也按这四条来，不要先从 IDE 配置查起。

## 如果第一次调试失败，先别做什么

第一次失败时，先不要马上：

- 重装整个模块项目
- 大改工作流逻辑
- 怀疑所有依赖都坏了

先回头核对：

1. 模块来源
2. 策略字段
3. 作业绑定关系
4. 调试入口是否出现在正确作业上

对小白来说，这个排查顺序通常比直接改代码更有效。
