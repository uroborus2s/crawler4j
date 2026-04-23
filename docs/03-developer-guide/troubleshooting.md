# 常见问题

这一页按“运行与交付主线”排问题。先判断你卡在模块工程、DevLink/ATM、Hosted UI、ZIP 交付，还是宿主安装/升级，再看对应条目。

## 最短定位顺序

1. CLI 不通过：先看 `check`、模块根目录和 `module.yaml`
2. DevLink 不生效：先看模块来源是不是 `开发链接`
3. ATM 跑不对：先看作业绑定的模块和 workflow
4. 页面空白：先看 `declare_ui()` 和 `check full`
5. 正式安装失败：先看 ZIP 结构和 `upgrade_source.repo`
6. 升级不生效：先看模块是否处于正式安装态、远端 Release 是否存在 ZIP 资产

## `uv run crawler4j check <level>` 不通过

确认：

- 当前目录下有 `module.yaml`
- `module.yaml.version` 是合法语义化版本
- `module.yaml.upgrade_source.repo` 是合法的 `owner/repo`
- `ui_extension.pages[]` 只包含 `id`、`label`、`icon`

处理：

- 先执行 `uv run crawler4j check full`
- 按错误逐项改 `module.yaml` 或 `module_runtime.py`
- 不要带着已知 gate 错误继续写业务代码

## Hosted UI 页面是空白

确认：

1. `module.yaml.ui_extension.pages[]` 是否存在对应页面
2. `module_runtime.py` 是否存在同步 `declare_ui()`
3. `uv run crawler4j check full` 是否通过
4. 是否真的调用了 `ui.declare_page`
5. `load_handler` 是否存在、是否为同步函数

处理：

- 先修声明链，再回宿主刷新页面
- 不要一上来就猜 UI 缓存

## 表格没有数据

确认：

1. `DataTable.data_source.type` 是不是 `binding` / `rows` / `query_handler`
2. 如果是 `binding`，`load_handler` 返回值里是否真的有对应字段
3. 如果是 `query_handler`，函数是否存在且签名是 `(context, table_id, query, params=None)`
4. `db.list_records` / `db.query_view` 返回的数据是不是对象数组

处理：

- `binding` 路径先打印 `load_handler` 返回值
- `query_handler` 路径先跑 `check full`
- 不要把业务逻辑塞进宿主 UI 侧找问题

## `open_page` 没跳转或参数不对

确认：

1. `page_id` 是否真的存在于 `ui_extension.pages[]`
2. `params` 是否使用了合法 `binding` 或固定 `value`
3. 目标页的 `load_handler(context, page_id, params=None)` 是否真正读取了 `params`

处理：

- 先确认页面 ID
- 再确认 params 映射
- 最后确认目标页读取逻辑
