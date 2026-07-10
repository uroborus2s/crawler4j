# Task 1 Contracts 与 SDK 验证证据

- Work item：CR-018 / TASK-036 / task 1
- Actor：`implement_contracts_sdk`
- 初次时间：2026-07-10 12:48:40 +0800
- Spec Review 修复时间：2026-07-10 12:58:23 +0800
- 状态：green

## Red

```bash
uv run pytest packages/crawler4j/tests/unit/test_sdk/test_hosted_ui_card.py packages/crawler4j/tests/unit/test_sdk/test_v2_scanner_diagnostics.py -q -p no:cacheprovider
```

真实结果：exit code `1`，`24 failed, 51 passed in 0.76s`。

失败原因符合预期：Contracts 尚不识别 `selection_mode`、`bulk_update_handler`、`toolbar.bulk_update`，scanner 尚未扫描批量 handler 的配置、引用、签名与参数类型。

补充边界 Red：

```bash
uv run pytest packages/crawler4j/tests/unit/test_sdk/test_hosted_ui_card.py::test_normalize_page_schema_rejects_invalid_crud_selection_mode -q -p no:cacheprovider
```

真实结果：exit code `1`，`1 failed, 1 passed in 0.04s`；显式空字符串被错误当作省略值，失败原因符合预期。

## 初次 Green

```bash
uv run pytest packages/crawler4j/tests/unit/test_sdk/test_hosted_ui_card.py packages/crawler4j/tests/unit/test_sdk/test_v2_scanner_diagnostics.py -q -p no:cacheprovider
```

真实结果：exit code `0`，`76 passed in 0.28s`；失败 `0`，错误 `0`，跳过 `0`。

## Spec Review 修复 1：`selection_mode` 移至 DataTable 顶层

Red：

```bash
uv run pytest packages/crawler4j/tests/unit/test_sdk/test_hosted_ui_card.py -q -p no:cacheprovider
```

真实结果：exit code `1`，`6 failed, 28 passed in 0.22s`。失败原因符合预期：DataTable 顶层拒绝 `selection_mode`、无 CRUD 表格没有默认 `single`，而 CRUD 内仍错误接受该字段。

Green：

```bash
uv run pytest packages/crawler4j/tests/unit/test_sdk/test_hosted_ui_card.py -q -p no:cacheprovider
```

真实结果：exit code `0`，`34 passed in 0.04s`；失败 `0`，错误 `0`，跳过 `0`。

## Spec Review 修复 2：`primary_keys` 必须恰好一个具体元素类型

Red：

```bash
uv run pytest packages/crawler4j/tests/unit/test_sdk/test_v2_scanner_diagnostics.py -q -p no:cacheprovider -k 'bulk_update_primary_key'
```

真实结果：exit code `1`，`3 failed, 10 passed, 35 deselected in 0.15s`。失败原因符合预期：模块内 `T = TypeVar("T")` 的 `List[T]`、`list[str, int]`、`List[str, int]` 尚未被拒绝。

Green：

```bash
uv run pytest packages/crawler4j/tests/unit/test_sdk/test_v2_scanner_diagnostics.py -q -p no:cacheprovider -k 'bulk_update_primary_key'
```

真实结果：exit code `0`，`13 passed, 35 deselected in 0.11s`；失败 `0`，错误 `0`，跳过 `0`。

## 最终 Green

```bash
uv run pytest packages/crawler4j/tests/unit/test_sdk/test_hosted_ui_card.py packages/crawler4j/tests/unit/test_sdk/test_v2_scanner_diagnostics.py -q -p no:cacheprovider
```

真实结果：exit code `0`，`82 passed in 0.27s`；失败 `0`，错误 `0`，跳过 `0`。

```bash
uv run ruff check packages/crawler4j-contracts/src/crawler4j_contracts/hosted_ui.py packages/crawler4j-sdk/src/v2_scanner.py packages/crawler4j/tests/unit/test_sdk/test_hosted_ui_card.py packages/crawler4j/tests/unit/test_sdk/test_v2_scanner_diagnostics.py
```

真实结果：exit code `0`，`All checks passed!`。

两条命令均出现既有 workspace 警告：`packages/.DS_Store` 不是目录；不影响 exit code 或验证结果。

## 需求核对

- `selection_mode`：位于 DataTable 顶层；覆盖所有表格省略默认 `single`、`none/single/multi`、非法值与空字符串拒绝，并拒绝嵌套在 CRUD 内。
- 批量入口显隐：覆盖 handler 存在时省略 `toolbar.bulk_update` 仍保留缺省状态，以及显式 `False` 原样保留。
- 配置约束：Contracts 与 scanner 覆盖 toolbar 开启却缺 handler、handler 缺 `primary_key`、handler 缺非空 `form.update_columns`。
- 引用与固定签名：覆盖缺失 `@ui_action` 引用，以及 `ctx`、错序、默认参数、keyword-only、`*args`、`**kwargs` 拒绝。
- `primary_keys`：覆盖接受 `list[str]`、`list[int]`、`List[str]`、`List[int]` 与自定义具体类型；拒绝无注解、裸 `list`、`list[Any]`、`Any`、`Mapping`、模块 TypeVar 和多元素类型参数。
- `payload`：覆盖拒绝裸 `dict`、`Mapping`、`Any`；既有 create/update/delete 正反例继续通过。

## 偏离与风险

- 未运行：全仓测试、Core/UI 测试。
- 原因：任务验证范围明确限定为两个 SDK 单元测试文件与四文件 ruff；Core/UI 不在 task 1 修改范围。
- 残余风险：task 1 仅证明 Contracts/scanner 契约；Core 渲染与调用链由相邻任务独立验证。

## 结论

`passed`
