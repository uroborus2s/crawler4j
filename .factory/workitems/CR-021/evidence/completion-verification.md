# Completion Evidence

## 基本信息

- Work item：`CR-021`
- Actor：`/root`
- 时间：2026-07-14T00:13:35+08:00
- 验证声明：CR-021 实现满足已确认需求，代码与 crawler4j 单元测试可进入独立评审。
- 结论：`passed`

## Red-Green

### Red

命令：

```bash
uv run pytest packages/crawler4j/tests/unit/test_core/test_rem/test_edit_env_dialog.py packages/crawler4j/tests/unit/test_core/test_rem/test_virtualbrowser_client.py::test_clear_cache_sends_only_browser_id packages/crawler4j/tests/unit/test_core/test_rem/test_provider.py::test_virtualbrowser_clear_cache_uses_external_browser_id packages/crawler4j/tests/unit/test_core/test_rem/test_proxy_binding.py::test_clear_env_cache_delegates_to_environment_provider packages/crawler4j/tests/unit/test_core/test_rem/test_env_list_widget.py::test_env_list_table_replaces_kind_with_created_at_and_keeps_compact_columns packages/crawler4j/tests/unit/test_core/test_rem/test_env_list_widget.py::test_env_list_widget_rows_show_fingerprint_browser_id -q
```

- 实际结果：`8 failed, 8 passed`，exit code `1`。
- 预期失败：原生下拉框、随机入口仍存在，Client/Provider/Manager 无 clear-cache 能力，列表无 external_id 列。
- 实际失败原因与预期匹配：是。

### Green

同范围加公共控件渲染用例：`19 passed in 0.80s`，exit code `0`。

新增 Provider 可见性与 API 失败传播后：

```bash
uv run pytest packages/crawler4j/tests/unit/test_core/test_rem/test_edit_env_dialog.py packages/crawler4j/tests/unit/test_core/test_rem/test_virtualbrowser_client.py -q
```

- 真实结果：`40 passed in 2.50s`，exit code `0`。

## 完整验证命令

```bash
uv run pytest packages/crawler4j/tests/unit -q
```

## 真实结果

- exit code：`0`
- 通过数量：`1198`
- 失败数量：`0`
- 错误数量：`0`
- 跳过数量：`0`
- 未运行项：真实 VirtualBrowser 在线清缓存、人工桌面 GUI 点击验收（已用 Qt 离屏渲染替代布局检查）。

真实输出摘要：

```text
........................................................................ [ 96%]
..............................................                           [100%]
1198 passed in 30.35s
```

静态检查：

```bash
uv run ruff check <本次 10 个 Python 变更文件>
```

- 真实结果：`All checks passed!`，exit code `0`。
- `git diff --check`：exit code `0`。

离屏视觉验收：

- 使用 Qt offscreen 渲染含两个当前池 IP 的 VirtualBrowser 编辑弹窗到 `/tmp/cr021-edit-env-dialog-fixed.png`。
- 真实尺寸输出：弹窗 `450x413`，下拉框 `40px`，相邻“应用所选 IP”按钮 `40px`，候选数 `2`。
- 图像检查：两个 IP 可展开选择；随机 IP 区域已移除；“缓存管理/清理缓存”布局完整；底部按钮未重叠或裁切。

## 独立评审修复验证

- 初审发现公共 `StyledComboBox` 样式字符串从 f-string 改为普通字符串后仍保留双花括号，Qt 样式解析失效；已改为合法单花括号，并在公共控件测试增加防回归断言。
- 初审发现任务契约未描述“未绑定池时从全部池首次绑定”的既有行为；已修正 task brief、实现报告和本证据，不改变既有功能。
- 修复后聚焦验证：`15 passed in 0.84s`，Ruff `All checks passed!`。
- 修复后完整验证：`1198 passed in 30.35s`，exit code `0`。

## 需求核对

- 公共下拉组件与 40px 等高：弹窗断言组件类型和实际最小高度；公共控件渲染测试通过。
- IP 语义：已绑定池时仅展示当前池内启用且未过期条目；未绑定池时保留全部池首次绑定能力；随机入口及 worker 分支删除。
- 清缓存：Client payload 与失败传播、Provider external_id、Manager 委托、UI provider 可见性与确认均有测试；worker 失败提示和并发序列化由代码路径与独立评审核对，未新增直接用例。
- 指纹浏览器 ID：表格 schema、搜索/排序配置及 row 映射有测试。

## 偏离

- `ruff format --check` 会要求格式化 5 个历史上未完全 Ruff-format 的大文件，差异主要是既有空白和全文件机械格式；为避免把无关改动混入本任务，没有执行全文件格式化。替代验证为 `ruff check` 与 `git diff --check`，两者通过。
- 未对真实 VirtualBrowser 环境执行清缓存，原因是该操作会修改用户外部环境状态。残余风险是厂商实际返回结构变化；实现会把非成功响应和响应正文明确反馈给用户。

## 结论

`passed`
