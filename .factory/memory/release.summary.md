# Release Summary

- Latest formal release tag: `v0.2.0` on 2026-04-20
- Current workspace root version: `0.0.0`
- Current app package version: `0.4.17`
- Runtime package version: `0.4.17`
- SDK version: `0.4.2`
- Contracts version: `0.4.2`

Evidence status:

- Root build: latest recorded wheel/sdist artifact passed on 2026-05-26 for `crawler4j 0.4.3`; current `crawler4j 0.4.17` wheel/sdist package build is not yet refreshed
- Desktop PyInstaller / macOS Sparkle bundle: passed on 2026-06-19 for `crawler4j 0.4.16`; old remote `Crawler4j-0.4.16.dmg` was removed, new `Crawler4j-0.4.16.dmg` / `appcast.xml` were generated and uploaded, public DMG `HEAD 200`, SHA256 `8463f4982ea4948a2151a7061449fc8a3fd9152848b37197a35504efb1f04243`
- SDK build/publish: passed on 2026-06-15 for current `crawler4j-sdk 0.4.2`; wheel/sdist uploaded to PyPI
- Contracts build/publish: passed on 2026-06-15 for current `crawler4j-contracts 0.4.2`; wheel/sdist uploaded to PyPI
- Full test/lint gate: historical full gate passed on 2026-05-18 for the 0.4.2 root version bump; 0.4.16 source proxy host-port matching repair scope passed REM source proxy / environment list / version regression `54 passed`, target `ruff check`, `uv lock --check`, `.factory/project.json` JSON validation, and `git diff --check`; 2026-06-19 packaging regression passed `65 passed` plus `uv lock --check`; current 0.4.17 task-monitor disable / REM fixed-job safety scope passed version service / ATM / Debug / REM focused regression `115 passed`, target `ruff check`, `uv lock --check`, `.factory/project.json` JSON validation, and `git diff --check`
- UI / CLI smoke: passed on 2026-05-01; `uv run python scripts/smoke_test_ui.py` and `uv run python -m crawler4j_sdk.cli.commands --help` passed
- Docs validate: not rerun in this documentation-memory sync turn

Release decision:

- Local code quality gate: PASS for the current 0.4.17 task-monitor disable / REM fixed-job safety branch
- Production release gate: partial for 0.4.x macOS internal update history; No-Go for full cross-platform production until `ctrip` real-site DevLink + ZIP E2E evidence, Windows real-machine signing/install/self-update evidence, Git tag / GitHub release assets, and formal delivery batch are closed
