# Task 1 Implementation Report

- Work item：`CR-021`
- 实现者：`/root`
- 状态：`approved_pending_commit`

## 实现

- `EditEnvDialog` 改用 `StyledComboBox(min_height=40)`；公共组件改为通过 Qt 属性设置最小高度，避免样式边框把 40px 计算成 42px。
- 删除“随机更换 IP”按钮、确认动作、worker 分支及相关参数；已绑定池时保持当前池过滤，未绑定池时保留从全部池首次选择的既有能力。
- 新增 VirtualBrowser 缓存管理区和普通确认框；仅 `virtualbrowser` 显示。
- 新增 `EnvironmentManager.clear_env_cache()`、Provider 能力和 `VirtualBrowserClient.clear_cache()`，请求 `/api/clearCache` 且 payload 仅为浏览器 ID；API 失败原样进入异常反馈链路。
- 环境列表新增 `external_id` schema 与行映射，列名为“指纹浏览器 ID”，空值显示 `-`。

## 测试

- 新增/调整弹窗公共组件、等高、随机入口删除、清缓存可见性/确认/worker 测试。
- 新增 Client 请求 payload 和失败传播测试。
- 新增 Provider 外部 ID、Manager 委托测试。
- 新增环境列表 schema 和 external ID 映射测试，并同步列索引断言。

## 边界

- 已绑定池的环境未改为跨池 IP 选择；未绑定池环境仍可从全部池进行首次绑定。用户已确认停用 IP 不可见符合预期。
- 未真实调用本机 VirtualBrowser 服务，避免清理真实用户环境缓存；API 契约通过隔离 Client/Provider 测试验证。
- 不自动关闭正在运行的环境；厂商拒绝时显示失败。
