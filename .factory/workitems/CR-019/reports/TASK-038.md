# TASK-038 实现报告

- 状态：`ready_for_review`
- Work item：`CR-019`
- Task：`TASK-038`

## 实现

- `ManagedPageRenderer._handle_table_row_action` 识别扁平行按钮 spec 的 `type="open_page"`，复用既有 `_handle_row_action` 后立即返回。
- 未声明或未知 `type` 的按钮继续进入既有 `ui_action` 路径；CRUD 编辑 / 删除分支不变。
- 新增回归锁定点击第二行、当前行参数、无同名 `ui_action` 调用和无源表刷新。
- 0.4.0 开发者文档补充行按钮 schema、参数和多选表格推荐用法。

## 范围与风险

- 未修改 `SkyDataTable`、Contracts、SDK scanner、版本号或发布文件。
- 动态行 action 仍不做新的静态扫描；本轮只复用现有受控 `binding/value` 参数解析。
- 全局 tasks/tests summary 在执行期间被独立发布任务修改，为避免覆盖或混入其未提交改动，本任务改写独立 `.factory/memory/cr-019.summary.md`。

