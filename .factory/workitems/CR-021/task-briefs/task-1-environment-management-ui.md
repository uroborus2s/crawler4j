# Task 1：环境编辑与 VirtualBrowser 管理能力

- Work item：`CR-021`
- 状态：`approved_pending_commit`
- 人工确认：用户确认停用 IP 不进入候选框符合预期，并批准按方案修改。

## 需求

1. 环境编辑弹窗使用公共下拉组件，并与相邻按钮统一为 40px 最小高度。
2. 已绑定 IP 池时，候选仅展示该池内 `available` 且未过期的条目；未绑定池时保留从全部池选择可用 IP 进行首次绑定的既有能力。保留明确选择并应用，删除“随机更换 IP”入口及执行分支。
3. VirtualBrowser 环境提供“清理缓存”操作，调用 `POST /api/clearCache`，请求体仅包含外部浏览器 ID；只清 Cache 与 Code Cache，不删除 Cookie，不自动停止运行中的环境，并向 UI 传播失败。
4. 非 VirtualBrowser 环境不展示清缓存入口。
5. 环境列表新增“指纹浏览器 ID”列，展示 `Environment.external_id`，缺失时显示 `-`，支持搜索和排序。

## 允许修改范围

- `packages/crawler4j/src/core/rem/manager.py`
- `packages/crawler4j/src/core/rem/provider.py`
- `packages/crawler4j/src/core/rem/ui/edit_env_dialog.py`
- `packages/crawler4j/src/core/rem/ui/env_list_widget.py`
- `packages/crawler4j/src/ui/components/combo_box.py`
- 对应单元测试与 `CR-021` 工厂证据、报告、memory。

## 验收

- 定向测试由 RED 失败转为 GREEN。
- 相关 UI、Provider、Manager 和公共控件测试通过。
- crawler4j 完整单元测试通过。
- Ruff 静态检查通过。
- 独立 reviewer 无 Critical / Important 阻塞项。
