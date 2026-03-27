# 模块开发指南

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** 对 `crawler4j` 一无所知的外部模块开发者 | Core 维护者 | QA  
**上游输入：** `crawler4j_sdk/cli/commands.py` | `crawler4j_sdk/cli/templates.py` | `src/core/mms/registry.py` | `src/core/atm/execution_runner.py` | `src/core/debug/service.py`  
**下游输出：** 外部模块项目 | 模块交付 zip | 模块开发验收记录  
**关联 ID：** `TASK-010`, `REQ-003`, `REQ-005`, `DOC-002`  
**最后更新：** 2026-03-28  

## 1. 这份指南是写给谁的

这份指南默认把读者当成下面这种开发者：

- 会基本的 Python 和命令行
- 但没有接触过 `crawler4j`
- 不知道模块怎么被宿主识别、执行、调试和安装
- 希望通过一份文档，尽量少试错地完成第一个模块

如果你正好属于这种情况，这份文档就是按你的视角来写的。

## 2. 这份指南解决什么问题

它解决的是“从零开始开发并交付一个 `crawler4j` 模块”的问题，而不是“如何修改 `crawler4j` Core 自身代码”的问题。

你顺着目录读完后，目标是能独立完成下面这条链路：

```text
创建模块项目
-> 编写 TaskScript / TaskFlow
-> 配置 module.yaml 与 UI
-> 用 DevLink 接进 Core 调试
-> 打包 zip
-> 在宿主应用里完成正式安装验收
```

## 3. 读这份指南之前你需要知道什么

你不需要先读懂整个仓库，也不需要先看完架构设计文档。  
你只需要接受下面三个前提：

1. 模块不是独立应用，而是由宿主 `crawler4j` 调度和运行的 Python 包。
2. 真正影响模块能否运行的，是 `module.yaml`、根 `__init__.py`、策略配置和模块来源。
3. 开发调试和正式交付是两条不同链路：开发看 `DevLink`，交付看 zip 安装。

这三个前提会在后面的章节里反复出现。

## 4. 术语约定

- `model`
  CLI 和历史文档里的创建命令名，当前仍保留在 `crawler4j init-model`。
- `module`
  Core 运行时、`module.yaml`、模块管理、调试与安装链路中的正式术语。
- `plugin`
  面向一般开发者更容易理解的泛称。当前项目里如果没有特别说明，可以把它理解为“外部模块”。

为了减少歧义，后文统一使用“模块”。

## 5. 推荐阅读方式

### 如果你完全是第一次接触

请按下面顺序读：

1. [01 概念与约束](./01-concepts/index.md)
2. [02 快速开始](./02-quickstart/index.md)
3. [03 项目结构与契约](./03-project-structure/index.md)
4. [04 模块开发](./04-development/index.md)
5. [05 调试](./05-debugging/index.md)
6. [06 交付与验收](./06-delivery/index.md)
7. [07 排错](./07-troubleshooting/index.md)

### 如果你只想先跑通第一个模块

先读：

1. [02 快速开始](./02-quickstart/index.md)
2. [05 调试](./05-debugging/index.md)
3. [06 交付与验收](./06-delivery/index.md)

### 如果你已经能跑通，但经常踩坑

重点看：

1. [03 项目结构与契约](./03-project-structure/index.md)
2. [06 交付与验收](./06-delivery/index.md)
3. [07 排错](./07-troubleshooting/index.md)

## 6. 读完之后你应该能做到什么

完成本指南后，你至少应当能独立完成以下事项：

1. 使用 `crawler4j-sdk` CLI 创建标准模块项目。
2. 理解 `module.yaml`、根 `__init__.py`、`tasks/`、`workflows/` 的职责分工。
3. 写出一个最小可运行的 `TaskScript` 和 `TaskFlow`。
4. 正确把模块注册成 `DevLink`，并在 ATM 中发起真实调试会话。
5. 打出符合宿主安装要求的 zip，并完成一次正式安装 smoke。

## 7. 如果你只记住一件事

请记住这一句：

> `crawler4j` 模块开发的主线不是“写完 Python 代码”，而是“让宿主正确识别、调试并安装你的模块”。

很多新手卡住，不是因为 Python 不会写，而是因为只盯着源码，没有同时看：

- `module.yaml`
- 根 `__init__.py`
- `DevLink`
- `execution.module`
- zip 安装结构

## 8. 文档目录

- [01 概念与约束](./01-concepts/index.md)
- [02 快速开始](./02-quickstart/index.md)
- [03 项目结构与契约](./03-project-structure/index.md)
- [04 模块开发](./04-development/index.md)
- [05 调试](./05-debugging/index.md)
- [06 交付与验收](./06-delivery/index.md)
- [07 排错](./07-troubleshooting/index.md)

## 9. 最短成功路径

如果你现在只关心“最快把一个模块跑起来”，可以先照着下面这条路径做：

```text
uvx --from crawler4j-sdk==1.0.3 crawler4j init-model hotel_demo
-> cd hotel_demo
-> uv run crawler4j new fetch_hotels
-> uv run crawler4j add-workflow sync_hotels
-> uv run crawler4j add-ui
-> 在 Core 中注册 DevLink
-> 用策略把 execution.module / execution.workflow 指向你的模块
-> 在 ATM 中点击调试
-> 打 zip 并安装验收
```

这条路径能帮你快速开始，但不等于你已经真正理解了模块契约。  
如果你要把模块交给别人用，仍建议完整阅读 [03 项目结构与契约](./03-project-structure/index.md) 和 [06 交付与验收](./06-delivery/index.md)。

## 10. 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-03-28 | 将原单文件指南重构为目录化章节指南，并按“小白开发者”视角扩写说明 | Codex |
| 2026-03-26 | 初版重写模块开发指南 | Codex |
