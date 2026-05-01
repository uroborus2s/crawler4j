# Release Summary

- Latest formal release tag: `v0.2.0` on 2026-04-20
- Current workspace root version: `0.0.0`
- Current app package version: `0.4.0`
- Runtime package version: `0.4.0`
- SDK version: `0.4.0`
- Contracts version: `0.4.0`

Evidence status:

- Root build: passed on 2026-05-01 for current `crawler4j 0.4.0`; wheel/sdist generated under `packages/crawler4j/dist/`
- Desktop PyInstaller bundle: passed on 2026-05-01 after QScintilla dependency line; macOS `.app` generated under `packages/crawler4j/dist/desktop/macos/Crawler4j.app`
- SDK build/publish: build passed on 2026-05-01 for current `crawler4j-sdk 0.4.0`; publish evidence is still pending
- Contracts build/publish: build passed on 2026-05-01 for current `crawler4j-contracts 0.4.0`; publish evidence is still pending
- Full test/lint gate: passed on 2026-05-01; `uv run pytest -q -p no:cacheprovider` => `886 passed`, `uv run ruff check .` and `git diff --check` passed
- UI / CLI smoke: passed on 2026-05-01; `uv run python scripts/smoke_test_ui.py` and `uv run python -m crawler4j_sdk.cli.commands --help` passed
- Docs validate: not rerun in this documentation-memory sync turn

Release decision:

- Local code quality gate: PASS for 0.4.0 review scope
- Production release gate: No-Go until `ctrip` real-site DevLink + ZIP E2E evidence, Windows real-machine signing/install/self-update evidence, publish evidence, and formal delivery batch are closed
