# CR-018 / TASK-036 整体验证证据

- 日期：2026-07-10（Asia/Shanghai）
- Actor：Codex Task 3 implementer
- 状态：`partial`（目标集 green；全量 unit 保留范围外 concern）
- Work item gate：`human_approved / ready_for_commit`

## 验证声明

验证 `CR-018` 的 Contracts / SDK / Core / UI 通用批量编辑改动、正式文档和工厂元数据；不验证具体业务模块 handler、业务分组规则、真实数据库写入或真实站点 E2E。

## 子任务独立评审证据

- Task 1 Contracts / SDK：独立 Spec + Quality Review `approved`；`82 passed`，Quality `100/100`。
- Task 2 Core / UI：独立 Spec + Quality Review `approved`；`38 passed`，Quality `98/100`。
- 评审路径：`.factory/workitems/CR-018/reviews/task-1-spec-review.md`、`task-1-review.md`、`task-2-spec-review.md`、`task-2-review.md`。

## Task 3 新鲜验证

### 1. 全量 unit

```bash
QT_QPA_PLATFORM=offscreen uv run pytest packages/crawler4j/tests/unit -q -p no:cacheprovider
```

- 沙箱内首次执行：exit code `2`，uv 缓存 `/Users/uroborus/.cache/uv/sdists-v9/.git` 权限被拒；未作为产品测试结果。
- 获准环境按原命令重跑：exit code `1`；最终文档 / evidence 落盘后再次按原命令复跑，exit code 仍为 `1`。
- 最终新鲜结果：`1132 passed, 2 failed in 28.06s`（前一次同样为 `1132 passed, 2 failed in 28.45s`）。
- errors：`0`；skipped：`0`。
- failures：
  - `test_sdk_readme_dependency_example_matches_generated_compatibility_ranges`：`packages/crawler4j-sdk/pyproject.toml` 为 `0.4.3`，README 仍写 `crawler4j-sdk>=0.4.2,<0.5.0`。
  - `test_workspace_release_docs_reflect_current_versions_and_publish_order`：`packages/crawler4j/pyproject.toml` 为 `0.4.29`，根 README 未包含对应版本表项。

归因：两个失败都位于版本 / 发布文档一致性测试；相关 pyproject 与 README 不在 `CR-018` diff，也不在 Task 3 允许修改范围。本任务明确禁止修改版本，因此未用范围外改动掩盖失败。该结果使整体 verification 保持 `partial`。

### 2. CR-018 合并目标集（补充分诊）

```bash
QT_QPA_PLATFORM=offscreen uv run pytest packages/crawler4j/tests/unit/test_sdk/test_hosted_ui_card.py packages/crawler4j/tests/unit/test_sdk/test_v2_scanner_diagnostics.py packages/crawler4j/tests/unit/test_core/test_mms/test_managed_page_renderer.py packages/crawler4j/tests/unit/test_ui/test_data_table.py -q -p no:cacheprovider
```

- exit code：`0`
- 结果：`120 passed in 1.51s`
- failures / errors / skipped：`0 / 0 / 0`

### 3. 目标 Ruff

```bash
uv run ruff check packages/crawler4j-contracts/src/crawler4j_contracts/hosted_ui.py packages/crawler4j-sdk/src/v2_scanner.py packages/crawler4j/src/core/mms/ui/managed_page_renderer.py packages/crawler4j/src/ui/components/data_table.py packages/crawler4j/tests/unit/test_sdk/test_hosted_ui_card.py packages/crawler4j/tests/unit/test_sdk/test_v2_scanner_diagnostics.py packages/crawler4j/tests/unit/test_core/test_mms/test_managed_page_renderer.py packages/crawler4j/tests/unit/test_ui/test_data_table.py
```

- exit code：`0`
- 结果：`All checks passed!`

### 4. Diff whitespace

```bash
git diff --check
```

- exit code：`0`
- 输出：空。

### 5. Project JSON

```bash
uv run python -m json.tool .factory/project.json
```

- 沙箱内首次执行：exit code `2`，同一 uv 缓存权限问题。
- 获准环境按原命令重跑：exit code `0`；JSON 完整解析。

### 6. 正式文档结构

```bash
uvx --from docs-stratego docs-stratego source validate --repo-path .
```

- 沙箱内首次执行：exit code `2`，同一 uv 缓存权限问题。
- 获准环境按原命令重跑：exit code `0`。
- 结果：`crawler4j: home_access=public pages=86 contracts=0 docs_root=.../crawler4j/docs`。

所有获准环境命令均出现既有 `packages/.DS_Store` 非目录 workspace member warning；未改变相应 exit code。

## 需求核对

- `selection_mode` 顶层 `none/single/multi` 与省略 `single`：已由 Contracts / Core 测试覆盖。
- bulk 配置、handler 引用、精确签名与具体类型：已由 Contracts / SDK scanner 覆盖。
- Core 只传 `primary_keys + payload`；保序、类型敏感去重；缺主键不调用：已覆盖。
- 0/1/多行按钮、单条 toolbar、行内点击行：已覆盖。
- 空白可空文本、同步 / 异步成功失败和非阻塞 dialog：已覆盖。
- 刷新、搜索、筛选、排序与分页清选择：已覆盖。
- 业务模块规则、`ctx.db` 写入与真实站点 E2E：未运行，且明确不在本 work item 范围。

## 结论

`CR-018` 目标改动与目标测试为 green，正式文档和 memory 已同步；全量 unit 因两个范围外版本 README 漂移失败而不能声明 verification passed。独立整体评审已通过，用户已于 2026-07-10 明确确认进入提交与 Contracts / SDK 发布流程；本证据不声明具体业务模块 E2E 或 PyPI 发布已经完成。

## 人工确认后的提交前复验

- 时间：2026-07-10 14:14（Asia/Shanghai）。
- 用户确认：明确要求升级 Contracts 0.4.3、SDK 0.4.4 并发布到 PyPI。
- 合并目标集：原命令新鲜复跑，exit code `0`，`120 passed in 1.41s`。
- 目标 Ruff：原命令新鲜复跑，exit code `0`，`All checks passed!`。
- `git diff --check`：exit code `0`。
- `.factory/project.json`：`python -m json.tool` exit code `0`。
- 正式文档结构：`docs-stratego source validate` exit code `0`，`pages=86 contracts=0`。

## 发布后补充

- `TASK-037` 已修正当时保留的两个版本 / README 漂移失败，最终全量 unit 为 `1134 passed`。
- Contracts 0.4.3 / SDK 0.4.4 已按依赖顺序发布，并通过 PyPI 文件哈希与隔离安装验证。
- 发布证据：`.factory/workitems/TASK-037/evidence/release.md`。
