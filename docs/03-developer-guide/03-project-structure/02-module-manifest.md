# 3.2 `module.yaml` 清单契约

## 推荐的最小写法

```yaml
name: hotel_demo
version: 1.0.0
display_name: Hotel Demo
description: 示例模块
author: crawler4j
sdk_version_range: ">=2.0.0"

ui_extension:
  type: declarative
  entry: config_schema.json
  nav_item:
    icon: "🧩"
    label: "Hotel Demo 配置"

workflows:
  - name: main_workflow
    display_name: 主工作流
    description: 默认工作流
```

如果你完全不知道该怎么写，第一次就从这个最小模板开始。不要一开始就往里面塞很多自定义字段。

## 关键字段解释

### `name`

运行时模块 ID。任务运行模板里的 `execution.module` 必须填这个值，而不是显示名、目录名别名或 zip 文件名。

对新手来说，这个字段几乎是最重要的字段。因为它同时影响：

- 宿主如何识别模块
- DevLink 如何映射模块名
- 任务运行模板如何找到目标模块
- 正式安装后如何定位同名模块

如果你只把一个字段写对，优先把它写对。

### `version`

模块版本。它主要用于安装、覆盖和交付识别，不影响模块被 Core 发现的基本条件。

简单理解就是：

- `name` 更像“我是谁”
- `version` 更像“我现在是哪一版”

### `display_name`

给 UI 和日志看的友好名称。即使你不填，模块仍然可能被加载；但建议始终填写，便于模块管理页面识别。

第一次开发模块时，建议把 `display_name` 写成对人更友好的名字，而不是和 `name` 一样的技术标识符。

### `sdk_version_range`

SDK 兼容范围。当前扫描器最稳定支持的是简单的 `>=x.y.z` 格式，因此建议写成：

```yaml
sdk_version_range: ">=2.0.0"
```

第一次开发模块时，照着这个格式写就够了。不要把版本范围写成一大串复杂表达式，然后再猜宿主到底怎么判断兼容。
如果你在升级旧模块，不要只改清单版本号；先把代码里的旧 `DataService` / 旧聚合接口写法改掉，再提升这里的范围。

### `workflows`

这里声明宿主可以选用的工作流。如果你在 `workflows/` 目录里写了 Python 文件，却没有同步更新 `module.yaml.workflows`，宿主侧配置与理解会出现偏差。

对新手来说，可以把这里理解成：

> “宿主看得见的工作流名单”

不是所有目录里的 Python 文件都会自动变成“可配置的正式工作流说明”。

### `ui_extension`

声明模块 UI 扩展入口。对于第一次开发模块的人，推荐先用：

```yaml
type: declarative
entry: config_schema.json
```

第一次开发模块时，这个字段的目标不是“炫”，而是“稳”。先让配置入口清晰可见，比一开始追求复杂 UI 更重要。

## 当前实现里的校验点

根据当前扫描器实现，以下规则会直接影响扫描结果：

1. `name` 必填
2. 模块名建议只使用小写字母、数字、下划线
3. 工作流名称不能重复
4. `sdk_version_range` 必须与当前 SDK 兼容

其中第 2 条当前更接近“强烈告警”而不是“强制失败”，但第一次开发模块时不要挑战这个边界。

### 新手最常见的三类写错方式

1. `name` 写成带空格或大小写混合
2. 工作流在 `workflows/` 里新增了，但 `module.yaml` 里忘了加
3. `sdk_version_range` 写了自己都说不清含义的复杂表达式

这三类问题都会让后面的调试、安装或任务配置变得更难排查。

## 关于目录名和 zip 根目录

当前运行时并不要求 zip 根目录名必须和 `module.yaml.name` 完全一致。  
但第一次交付模块时，仍然建议你让它们保持一致，原因很简单：

- 便于人类排查
- 便于 DevLink 和正式安装切换
- 便于交付物命名和版本管理

## 推荐做法

第一次开发模块时，优先遵守下面这组约束：

1. 目录名、包名、`module.yaml.name` 保持一致
2. `sdk_version_range` 用简单的 `>=2.0.0`
3. 每加一个工作流，都同步更新 `module.yaml`
4. 不要把复杂 UI 声明、实验性字段和历史遗留字段一起塞进去

这样能显著降低你在 DevLink、运行配置解析和 zip 安装时的排错成本。

## 小白写 `module.yaml` 的建议节奏

第一次写时，建议按下面顺序填：

1. 先填 `name`
2. 再填 `version`
3. 再填 `display_name`、`description`
4. 再填 `sdk_version_range`
5. 再填 `workflows`
6. 最后再补 `ui_extension`

这样你每一步都知道自己在解决什么问题，不容易一口气把清单写乱。
