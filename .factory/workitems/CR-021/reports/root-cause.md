# Root Cause Investigation

## 基本信息

- Work item：`CR-021`
- 问题来源：用户截图和明确变更要求
- 受影响路径：环境编辑弹窗、VirtualBrowser Client/Provider、环境列表
- 当前状态：`fix_verified_and_reviewed`

## 现象

- Bug 症状：按钮与下拉框高度和视觉风格不协调；IP 下拉框无法查看其他 IP；界面存在没有必要的随机 IP 入口。
- 缺失能力：没有按环境清理 Chromium 缓存的入口；环境列表没有展示指纹浏览器 ID。
- 复现步骤：用同一池内两个可用、未过期 IP 创建弹窗；两项均可显示。将候选条目标记停用或设为已过期后，该条目被静默剔除。
- 失败证据：`.factory/workitems/CR-021/evidence/root-cause.md`
- 基线命令：相关 UI 单元测试 `42 passed`，表明这是现有契约遗漏而非测试执行失败。

## 调查

- 最近变化：提交 `31821ed0` 首次加入 IP 选择时就引入了停用/过期静默过滤；`c2961b65` 新增明确应用和随机更换双入口，但没有迁移到公共下拉组件。
- 可工作的相似实现：同仓 `import_existing_env_dialog.py`、`ip_pool_dialogs.py` 等通过 `StyledComboBox as QComboBox` 使用公共下拉组件。
- 差异：本弹窗从 `PyQt6.QtWidgets` 直接导入 `QComboBox`；公共按钮默认 40px，而原生下拉框未统一高度。
- 数据流：`Environment.proxy_config.pool_id` → 当前 `IPPool.entries` → `is_available()` 与 `is_expired()` 双重过滤 → 写入下拉框。
- 边界证据：Manager 的 `update_env(proxy_entry_id=...)` 已能把任意可用 IP 条目及其真实 `pool_id` 绑定到环境，因此 UI 跨池展示不会突破 Manager 约束。

## 根因

- 直接原因 1：弹窗混用了公共 `StyledButton` 与原生 `QComboBox`，控件高度和主题不一致。
- 已排除原因：仅仅“限制在当前 pool_id”不能解释当前池内条目缺失；同池双条目测试已通过。
- 直接原因 2：弹窗静默隐藏停用或已过期条目，而 IP 池页面的“状态”只反映人工启用/停用，过期条目仍可能显示为“可用”，两个界面对“可用”的含义不一致。
- 直接原因 3：上一版在已有明确选择动作之外继续保留随机分配动作，形成重复且含义不透明的入口。
- 直接原因 4：VirtualBrowser 的 `clearCache` endpoint 尚未进入 Client/Provider/Manager/UI 调用链。
- 直接原因 5：环境模型已有 `external_id`，表格 schema/row 映射遗漏了这一字段。
- 根源原因：IP 条目的人工状态与时间有效性是两个字段，但 UI 没有统一派生“当前可选”状态，也没有在候选为空或减少时解释过滤原因。
- 最小假设：截图实例中其他同池条目被 `disabled` 或 `expires_at` 过滤；若 IP 池页面仍显示“可用”，则以 `expires_at` 过滤为首要假设。
- 假设验证：代码和聚焦测试已把范围缩小；截图实例数据不在当前数据库，尚缺条目 `status/expires_at` 证据。

## 修复方案候选

- 弹窗：改用 `StyledComboBox(min_height=40)`，与相邻按钮等高；已绑定池时保持当前池并过滤停用或已过期条目，未绑定池时保留从全部池首次绑定的既有能力。
- 代理操作：移除 `refresh_proxy` worker 分支、按钮、确认框和旧测试，仅保留明确选择后应用。
- 缓存：在 `VirtualBrowserClient` 新增 `clear_cache(browser_id)`；由 VirtualBrowser Provider 暴露清缓存能力，Manager 按环境调用；弹窗仅对 `virtualbrowser` 显示“清理缓存”，并保留确认与错误反馈。
- 列表：新增“指纹浏览器 ID”列，值取 `env.external_id`，非 VirtualBrowser 或缺失时显示 `-`。
- 防回归：覆盖公共组件与等高、同池正常/停用/过期条目的显示语义和原因、随机入口删除、`clearCache` 请求 payload/错误语义、按钮 provider 可见性、external_id 列映射。
- 是否涉及兜底 / 降级：否；不复用语义更重的 `/api/deleteBrowserData`，不吞 API 错误。

## 结论

- 根因是否明确：代码过滤根因明确；截图实例具体命中停用还是过期不影响本次方案。
- 是否允许修复：是；用户确认停用 IP 不可查看符合预期，并批准按方案修改。
- 剩余风险：官方文档提示运行中的环境可能因缓存文件占用而清理失败；实现应保留明确错误，不擅自停止用户正在使用的环境。
