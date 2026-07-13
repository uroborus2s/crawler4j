# CR-021 根因证据

## 输入证据

- 截图：`/Users/uroborus/Downloads/屏幕截图 2026-07-13 233341.png`
- 截图显示“应用所选 IP”“随机更换 IP”“刷新指纹”等按钮为 40px 高，而可用 IP 下拉框是原生紧凑高度；下拉框只展示一个 IP。
- 用户明确要求删除随机 IP、增加缓存清理按钮，并在环境列表展示指纹浏览器 ID。

## 代码边界证据

1. `packages/crawler4j/src/core/rem/ui/edit_env_dialog.py`
   - 按钮统一实例化为 `StyledButton`。
   - IP 下拉框直接实例化为 PyQt6 原生 `QComboBox`，没有使用 `src.ui.components.combo_box.StyledComboBox`。
   - `_load_pool_entries()` 在环境已有 `pool_id` 时读取当前池全部内存条目，然后静默过滤 `not entry.is_available()` 或 `entry.is_expired()` 的条目。
   - 现有测试用同一池内两个可用、未过期条目验证第二项可以被选择，证明“限定当前池”不能解释当前池内条目缺失。
   - `refresh_proxy` 与“随机更换 IP”按钮是独立动作，和“选择 IP + 应用”同时存在。
2. `packages/crawler4j/src/ui/components/combo_box.py`
   - 已有公共 `StyledComboBox`，默认最小高度 32px，提供统一深色样式和下拉视图。
3. `packages/crawler4j/src/core/rem/models.py`
   - `Environment.external_id` 已持久化外部系统环境 ID，可直接作为指纹浏览器 ID 的事实源。
4. `packages/crawler4j/src/core/rem/ui/env_list_widget.py`
   - 当前表格 schema 和 `_build_table_row()` 都没有映射 `external_id`。
5. `packages/crawler4j/src/core/rem/provider.py`
   - `VirtualBrowserClient` 已实现 `/api/deleteBrowserData`，但没有实现只清 Chromium 缓存的 `/api/clearCache`。
   - 编辑弹窗 worker 只支持代理更新和指纹刷新，没有清理缓存动作。

## 反证与剩余分支

- 命令：`uv run pytest packages/crawler4j/tests/unit/test_core/test_rem/test_edit_env_dialog.py::test_edit_env_dialog_applies_selected_ip_with_explicit_button -q`
- 结果：`1 passed in 0.49s`。
- 结论：同池、`available`、未过期的两个条目会同时进入下拉框。
- 当前池内条目仍不显示时，代码只剩三类可能：条目被标为 `disabled`、`expires_at` 已过期，或运行实例持有的 `IPPoolManager` 快照中没有该条目。
- IP 池页面的“状态”列只显示人工 `available/disabled`，不会把 `expires_at` 已过期显示为“已过期”；因此过期条目仍可能在列表中呈现“可用”，但在编辑弹窗被静默剔除。这是已确认的语义不一致。
- IP 池页面和编辑弹窗通常读取同一个全局 Manager；若在同一进程、同一页面能看到条目，运行快照缺失的可能性低于过期过滤。

## 实例数据边界

- 截图环境 ID 为 `185`，当前本机 `~/Library/Application Support/Crawler4j/state.db` 的环境 ID 范围为 `621..1175`，没有环境 185。
- 当前本机数据库也不存在截图 IP `36.212.243.194`，因此截图来自另一份运行实例数据，无法在此处核对缺失条目的 `status/expires_at`。
- 在取得该实例 IP 池条目的状态与过期时间前，不能声称具体是 `disabled` 还是 `expired`。

## VirtualBrowser 官方 API 证据

- 文档：`https://virtualbrowser.cc/zh/api/clear-cache.html`
- 请求：`POST /api/clearCache`
- JSON：`{"id": <浏览器环境 ID>}`
- 语义：只清理指定环境的 Chromium `Cache` 与 `Code Cache`。
- 运行中缓存文件被占用时可能失败，文档建议先关闭环境再清理。

## 现有回归

- 命令：`uv run pytest packages/crawler4j/tests/unit/test_core/test_rem/test_edit_env_dialog.py packages/crawler4j/tests/unit/test_core/test_rem/test_env_list_widget.py -q`
- 结果：全文件基线 `42 passed in 1.09s`；同池双条目聚焦复现 `1 passed in 0.49s`。
- 说明：现有测试证明同池正常条目能够显示，但没有覆盖过期条目的用户可见原因、公共下拉组件、清理缓存或外部 ID 列。

## 人工确认

- 用户确认：“停用的ip无法查看？那现在没问题了，按照方案修改吧”。
- 决策：已绑定池时保持当前池范围及停用/过期过滤，不扩大到其他 IP 池；未绑定池时保留从全部池首次绑定的既有能力；继续实现其余已确认变更。
