# Release Summary

- Latest formal release tag: `v0.2.0` on 2026-04-20
- Current workspace root version: `0.0.0`
- Current app package version: `0.4.29` (not upgraded or published in this batch)
- Runtime package version: `0.4.29`
- SDK release candidate: `0.4.4`
- Contracts release candidate: `0.4.3`

Evidence status:

- Root build: latest recorded wheel/sdist artifact passed on 2026-05-26 for `crawler4j 0.4.3`; current `crawler4j 0.4.29` wheel/sdist package build is not yet refreshed
- Desktop PyInstaller / macOS Sparkle bundle: passed on 2026-06-19 for `crawler4j 0.4.16`; old remote `Crawler4j-0.4.16.dmg` was removed, new `Crawler4j-0.4.16.dmg` / `appcast.xml` were generated and uploaded, public DMG `HEAD 200`, SHA256 `8463f4982ea4948a2151a7061449fc8a3fd9152848b37197a35504efb1f04243`
- SDK build/publish: `crawler4j-sdk 0.4.4` wheel/sdist build and publish dry-run passed; PyPI publish pending
- Contracts build/publish: `crawler4j-contracts 0.4.3` wheel/sdist build and publish dry-run passed; PyPI publish pending and must precede SDK
- Full test/lint gate: 2026-07-10 release candidate full unit `1134 passed`; target Ruff, `uv lock --check`, `.factory/project.json` JSON validation, docs-stratego and `git diff --check` passed
- UI / CLI smoke: passed on 2026-05-01; `uv run python scripts/smoke_test_ui.py` and `uv run python -m crawler4j_sdk.cli.commands --help` passed
- Docs validate: not rerun in this documentation-memory sync turn

Release decision:

- Local code quality gate: PASS for the current 0.4.17 task-monitor disable / REM fixed-job safety branch
- Production release gate: partial for 0.4.x macOS internal update history; No-Go for full cross-platform production until `ctrip` real-site DevLink + ZIP E2E evidence, Windows real-machine signing/install/self-update evidence, Git tag / GitHub release assets, and formal delivery batch are closed
