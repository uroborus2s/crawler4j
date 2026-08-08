# TASK-045 验证证据

- 时间：2026-08-08
- 状态：`verification_passed_uncommitted`

| Gate | 命令 | 结果 |
| --- | --- | --- |
| TDD RED | 新增目标 unit 集 | exit 2；缺少 `EnvCandidateResult` 导出导致 collection error |
| 定向 unit + 版本/打包 | `uv run pytest <10 个变更目标 unit 文件> packages/crawler4j/tests/unit/test_sdk/test_packaging_config.py -q -p no:cacheprovider` | `320 passed` |
| 相邻 HTTP surface | `uv run pytest .../test_http_tools.py .../test_runtime_capabilities.py -q -p no:cacheprovider` | `56 passed` |
| SDK integration | `uv run pytest packages/crawler4j/tests/integration/test_sdk_cli_module_mode.py -q -p no:cacheprovider` | `12 passed` |
| acceptance | `uv run pytest packages/crawler4j/tests/acceptance -q -p no:cacheprovider` | `20 passed` |
| full unit | `uv run pytest packages/crawler4j/tests/unit -q -p no:cacheprovider` | `1287 passed` |
| lint | `uv run ruff check .` | `All checks passed` |
| lock | `uv lock --check` | exit 0，85 packages resolved |
| docs | `uvx --from docs-stratego docs-stratego source validate --repo-path .` | exit 0，`pages=87 contracts=0` |
| JSON/diff | `jq -e . .factory/project.json .factory/workitems/CR-025/ledger.jsonl` + `git diff --check` | exit 0 |
| Contracts build | `uv build --package crawler4j-contracts --out-dir /tmp/cr025-contracts-build` | wheel/sdist `0.4.5` 构建成功 |
| SDK build | `uv build --package crawler4j-sdk --out-dir /tmp/cr025-sdk-build` | wheel/sdist `0.4.6` 构建成功；METADATA 依赖 Contracts `>=0.4.5,<0.5.0` |
| Contracts wheel smoke | 隔离 venv 安装 `crawler4j_contracts-0.4.5` wheel 并导入/构造公开符号 | `EnvCandidateResult` 与 `TaskContext.candidate_context` 通过 |
| 独立复评 | `/root/cr025_plan_review` 只读复核功能整改与版本增量 | `100/100`，Critical/Important/Minor 均为 0 |
| 客户端版本 RED | 根应用 pyproject 提升到 `0.4.41` 后运行 packaging test | `1 failed, 64 passed`；根 README 仍是 `0.4.40` |
| 客户端版本 GREEN | `uv run pytest packages/crawler4j/tests/unit/test_sdk/test_packaging_config.py -q -p no:cacheprovider` | `65 passed` |
| Root build | `uv build --package crawler4j --out-dir /tmp/cr025-root-build` | `crawler4j-0.4.41` wheel/sdist 构建成功；METADATA 依赖 Contracts `>=0.4.5,<0.5.0` |
| 客户端版本独立复评 | `/root/cr025_plan_review` 只读增量复评 | `99/100`，Critical/Important 为 0；唯一日期 Minor 已修 |
| PR | GitHub PR #58（`0.4.0` → `main`） | 已合并，merge commit `c5e0788f` |
| Contracts 发布 | `uv publish` 后查询 PyPI JSON | `0.4.5` wheel/sdist SHA-256 与本地构建一致 |
| SDK 发布 | Contracts 上线后 `uv publish` 并查询 PyPI JSON | `0.4.6` 依赖 Contracts `>=0.4.5,<0.5.0`，wheel/sdist SHA-256 与本地构建一致 |
| PyPI 隔离安装 | 新 venv 安装 `crawler4j-sdk==0.4.6` | 自动解析 Contracts `0.4.5`；公开 API smoke 通过 |

全量首轮的单一失败来自既有 `test_http_tools.py` 仍断言 candidate surface 不得含 HTTP；这是本次公共契约变化的相邻测试，更新后相邻与全量均通过。

## 覆盖映射

- sync/async/awaitable 单次调用、异常和超时：MMS unit。
- 结构化 context、精确 64 KiB、多字节、NaN/Infinity、循环/非法值、敏感哨兵：MMS/ATM unit。
- 选中 workflow setup/run、固定 env、旧返回、空候选、租约后安全复核：ATM unit。
- async scanner 不执行 provider、manifest 单声明、full/package/verify：SDK unit/integration/acceptance。
- 公开版本与依赖：Contracts `0.4.5`、SDK `0.4.6`、SDK/Core 最低 Contracts `0.4.5`，由 packaging test、lock、wheel METADATA 和隔离导入覆盖。
