# CR-022 定向验证证据

## RED evidence

1. Contracts/SDK 新测试首次运行：`6 failed, 82 passed`；失败归因于公共 schema/type/export/scanner diagnostics 尚未实现。
2. Core Form 新测试首次运行：collection error `ModuleNotFoundError: src.core.mms.ui.hosted_form`；失败归因于 controller/registry 尚未实现。
3. Renderer 新测试首次运行：`6 failed, 24 deselected`；失败分别归因于 controller/default、滚动容器、standalone field 和 change dispatch 尚未实现。
4. 多列增量 RED：renderer `3 failed`，分别证明默认单列/三列网格尚未实现，以及 reset 后精确空字符串在提交读取时被旧 truthy 逻辑转换为 `None`。

## GREEN evidence

执行：

```bash
UV_CACHE_DIR=/tmp/crawler4j-uv-cache QT_QPA_PLATFORM=offscreen uv run pytest -q -p no:cacheprovider \
  packages/crawler4j/tests/unit/test_sdk/test_hosted_ui_card.py \
  packages/crawler4j/tests/unit/test_sdk/test_contracts_exports.py \
  packages/crawler4j/tests/unit/test_sdk/test_v2_scanner_diagnostics.py \
  packages/crawler4j/tests/unit/test_core/test_mms/test_hosted_form.py \
  packages/crawler4j/tests/unit/test_core/test_atm/test_runtime_capabilities.py \
  packages/crawler4j/tests/unit/test_core/test_mms/test_module_ui_runtime.py \
  packages/crawler4j/tests/unit/test_core/test_mms/test_managed_page_renderer.py
```

多列契约、Form liveness、精确空字符串提交与独立 review 修复后，2026-07-15 最终新鲜执行结果：`199 passed in 4.50s`，exit code `0`；独立 reviewer 同集复跑 `199 passed in 4.45s`，exit code `0`。review 修复覆盖 renderer 所在屏幕选择、合法超大 gap 的 Qt 安全收敛，以及对应 Contracts fixture 有效性。

目标 Ruff：`All checks passed!`，exit code `0`。

环境注记：默认 uv cache 位于 workspace sandbox 外，首次命令因权限被拒；后续统一显式使用 `/tmp/crawler4j-uv-cache`。这不是项目测试失败。

## Consumer-side integration evidence

消费模块维护方报告：本地 editable Contracts/SDK 下，三列 schema `crud.form.layout={"columns":3,"gap":12}` 被 manifest lock 精确保留，`crawler4j check full` 通过，模块定向 `262 passed`；其只读复核当前七个 Core 定向文件 `197 passed`、schema + renderer 子集 `81 passed`。该证据仅说明最终契约已完成真实下游联调，不代替 Core 最终验证，且本任务没有修改消费模块。
