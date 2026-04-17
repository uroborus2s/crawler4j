# 模块结构

这一页只回答三个问题:

1. 标准模块目录长什么样
2. 根入口、`module_runtime.py`、`module.yaml` 各自负责什么
3. 哪些字段和目录是正式契约，不能再发明第二套

## 标准目录

当前 `crawler4j module init` 生成的标准模块目录如下:

```text
hotel_demo/
├── __init__.py
├── .gitignore
├── .python-version
├── README.md
├── module.yaml
├── module_runtime.py
├── pyproject.toml
├── tasks/
├── tests/
├── ui/
└── workflows/
```

补一条最容易误解的事实:

- `utils/` 不是 CLI 默认生成目录
- 只有你确实有纯函数要复用时，再自己创建 `utils/`

## 每个路径负责什么

| 路径 | 职责 | 明确不要放什么 |
|---|---|---|
| `__init__.py` | 薄壳装配和必要导出 | 业务逻辑、配置解析 |
| `module.yaml` | 唯一静态清单 | 运行时状态、持久数据 |
| `module_runtime.py` | hook、环境选择器、`declare_ui`、很薄的 glue code | 领域转换、多步流程、批处理循环 |
| `tasks/` | 原子业务动作 | 完整流程编排 |
| `workflows/` | 流程编排 | 页面细节和大量字段解析 |
| `tests/` | 模块自己的最小回归测试 | 宿主内部实现细节、集成环境硬编码 |
| `ui/` | 代码型页面 | 第二套模块框架 |
| `utils/`（按需自建） | 轻量纯函数 | 再包一层宿主 API |

## 根 `__init__.py` 的纪律

当前根入口本质上只做三件事:

1. 创建 `ModuleAssembler`
2. 暴露统一 `run(context)` 入口
3. 代理标准 lifecycle hook

所以默认规则是:

- 不在这里写业务逻辑
- 不在这里做配置拼装
- 不在这里定义 workflow

### 唯一例外: 不要破坏标准根薄壳

如果你使用标准 CLI 脚手架，根 `__init__.py` 已经通过 `__getattr__` 自动转发 `module_runtime.py` 里的:

- `declare_ui`
- schema 里 `create_handler` / `update_handler` 指向的同名函数
- 其他生命周期 hook

这意味着:

- 标准模块通常不需要为了数据表再手改根 `__init__.py`
- 真正的要求不是“手工导出”，而是“不要破坏 SDK 托管的根薄壳”

安全边界直接记这 4 条:

- 安全: 不改 `__init__.py`
- 安全: 只改 `module_runtime.py`、`tasks/`、`workflows/`、`ui/`
- 危险: 删除 `__getattr__`
- 危险: 往根入口里新增业务逻辑、自定义导出或第二套装配代码

如果你怀疑根入口已经被改坏，最快核对方式不是猜，而是把它和当前 CLI 新生成模块的 `__init__.py` 对比一遍。

## `module_runtime.py` 只允许做薄胶水

`module_runtime.py` 只允许放:

- lifecycle hook
- 环境选择器
- `declare_ui`
- 很薄的 data table handler

如果你在这里开始写:

- 多步业务流程
- 批量处理循环
- 大段数据转换
- 类似 service / repository 的抽象

那通常已经写错位置了。

## `module.yaml` 是唯一静态清单

它负责:

- 模块身份
- 升级来源
- 工作流列表
- UI 入口
- 默认配置模板

它不负责:

- 持久化运行时配置
- 保存业务数据
- 描述 SDK 兼容范围

## 一个完整示例

```yaml
name: hotel_demo
version: 0.1.0
display_name: 酒店采集示例
description: 酒店业务模块
author: crawler4j
upgrade_source:
  type: github_release
  repo: your-org/hotel_demo
  allow_prerelease: false
workflows:
  - name: hotel_sync
    display_name: 酒店同步
    description: 抓取并刷新酒店列表
ui_extension:
  type: micro_app
  entry: ui:DashboardPage
  detail_menu:
    - id: hotels
      icon: 📋
      label: Hotels
      entry: core:data_table:hotels
config_defaults:
  module:
    city: shanghai
    page_size: 20
  workflows:
    hotel_sync:
      retry_enabled: false
```

## 重要字段说明

| 字段 | 必填 | 说明 |
|---|---|---|
| `name` | 是 | 模块名；必须是全小写合法 Python 标识符 |
| `version` | 建议 | 模块自身版本 |
| `display_name` | 建议 | 人类可读名称 |
| `description` | 建议 | 模块说明 |
| `author` | 可选 | 作者信息 |
| `upgrade_source` | 是 | 当前只支持 GitHub Release |
| `workflows` | 是 | 工作流列表，不能为空 |
| `ui_extension.type` | 否 | `none` 或 `micro_app` |
| `ui_extension.entry` | 条件必填 | 代码型页面入口，格式必须是 `ui:PageClass` |
| `ui_extension.detail_menu` | 可选 | 托管数据表详情页菜单 |
| `config_defaults` | 建议 | 默认配置模板 |

## `config_defaults` 和 `TaskScript.default_config` 不是一回事

这是新手最容易混的点:

| 名称 | 作用 | 生效时机 |
|---|---|---|
| `module.yaml.config_defaults` | 宿主初始化和“恢复默认”的静态模板 | 模块首次加载、手动恢复默认 |
| `TaskScript.default_config` | task 类自己声明的局部默认值 | task 自身语义层面的默认说明 |

简单记忆:

- 你要影响“宿主第一次初始化配置”，改 `config_defaults`
- 你要表达“这个 task 本身的局部默认值”，才考虑 `default_config`

## 命名规则

- 文件名: `snake_case`
- task 名: `snake_case`
- workflow 名: `snake_case`
- dataset / `view_id`: `snake_case`
- 类名: `PascalCase`
- 配置 key: `snake_case`

下一步建议看 [构建模块](build-modules.md)。
