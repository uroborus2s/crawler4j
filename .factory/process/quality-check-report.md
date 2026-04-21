# Quality Check Report

## Check Date

2026-04-22

## Results

| Check | Result | Detail |
|---|---|---|
| `uv run pytest -q` | PASS | `523 passed` after fixing external-module install rollback, queued REM refresh, and UI async validation gaps |
| `uv run ruff check .` | PASS | Full repo lint rechecked after the MMS install rollback fix and strengthened UI smoke/tests |
| UI smoke | PASS | `uv run python scripts/smoke_test_ui.py` now covers qasync Shell lifecycle + Dashboard async refresh instead of only bare `Shell()` instantiation |
| Workspace build | PASS | `uv run build` regenerated Root / SDK / Contracts wheels and sdists on 2026-04-21 |
| macOS PyInstaller bundle | PASS | `uv run package-desktop` 固定生成到 `packages/crawler4j/dist/desktop/macos/`，中间构建目录固定为 `packages/crawler4j/build/pyinstaller/macos/` |
| Windows Velopack targeted checks | PASS | `uv run pytest packages/crawler4j/tests/unit/test_core/test_system/test_update_service.py packages/crawler4j/tests/unit/test_ui/test_app.py packages/crawler4j/tests/unit/test_sdk/test_packaging_config.py -q` => `50 passed`，并已通过目标文件 `uv run ruff check ...` |
| Host DevLink list | PASS | `ctrip_crawler` 当前通过 DevLink 指向 `/Users/uroborus/PythonProject/ctrip_crawler`（沿用 2026-04-19 证据） |
| Fresh `ctrip` ZIP preview | PASS | `/tmp/ctrip_crawler-acceptance.zip` 通过 `host install preview --skip-remote-check`（沿用 2026-04-19 证据） |
| `ctrip` module `check full` | PASS | 当前模块源码 gate 通过（沿用 2026-04-19 证据） |
| `ctrip` module `uv run pytest -q` | PASS | `193 passed`（沿用 2026-04-19 证据） |

## Interpretation

- Current repo is green on the current workspace after the latest review-driven fixes.
- Formal SDK CLI and host ZIP preview chains remain reproducible on the retained `2026-04-19` baseline evidence.
- Current release gate is still `No-Go` because `ctrip` fresh real-site E2E evidence is incomplete, delivery batch / remote release evidence is not closed in this pass, and Windows still lacks real-machine signing / install / self-update evidence in the current batch.
