# TASK-012 补齐 MMS trust gate 与自定义页面加载

- 状态：DONE
- 类型：TASK
- 优先级：P1
- 估算：1.0 人/天
- 关联 ID：`TASK-012`, `CR-003`, `REQ-002`, `REQ-005`

## 目标

- 明确并实现代码型 UI 扩展的 trust gate / allowlist / 降级路径
- 让模块详情页对受支持的自定义页面声明进入真实加载链路
- 对不受信、未声明或加载失败的页面保持安全降级

## 验收标准

- 代码型 UI 扩展默认拒绝，只有受信来源或 allowlist 命中时才允许装载
- 自定义页面加载路径有明确错误处理与降级页面
- `core:data_table:*` 之外的受支持入口至少有一条真实加载链路
- 对 trust gate 与降级行为存在回归测试
- 文档与实现保持一致

## 完成说明

- 已新增 `src/core/mms/ui_loader.py`，统一处理 trust gate、allowlist 与自定义页面加载
- `detail_menu.entry: ui:SomePage` 已在 `ui_extension.type = micro_app` 下进入真实加载链路
- `ModuleDetailPage` 对未受信、缺少页面类或加载异常的情况都已降级为可解释的占位页
- 已补充 `tests/unit/test_core/test_mms/test_module_detail_page.py` 回归测试
