# Release Summary

- Latest formal release tag: `v0.2.0` on 2026-04-20
- Current workspace root version: `0.0.0`
- Current app package version: `0.4.16`
- Runtime package version: `0.4.16`
- SDK version: `0.4.2`
- Contracts version: `0.4.2`

Evidence status:

- Root build: latest recorded artifact passed on 2026-05-26 for `crawler4j 0.4.3`; current `crawler4j 0.4.16` package build is not yet refreshed
- Desktop PyInstaller / macOS Sparkle bundle: latest recorded artifact passed on 2026-05-26 for `crawler4j 0.4.3`; current `crawler4j 0.4.16` desktop bundle is not yet refreshed
- SDK build/publish: passed on 2026-06-15 for current `crawler4j-sdk 0.4.2`; wheel/sdist uploaded to PyPI
- Contracts build/publish: passed on 2026-06-15 for current `crawler4j-contracts 0.4.2`; wheel/sdist uploaded to PyPI
- Full test/lint gate: historical full gate passed on 2026-05-18 for the 0.4.2 root version bump; current 0.4.16 source proxy host-port matching repair scope passed REM source proxy / environment list / version regression `54 passed`, target `ruff check`, `uv lock --check`, `.factory/project.json` JSON validation, and `git diff --check`
- UI / CLI smoke: passed on 2026-05-01; `uv run python scripts/smoke_test_ui.py` and `uv run python -m crawler4j_sdk.cli.commands --help` passed
- Docs validate: not rerun in this documentation-memory sync turn

Release decision:

- Local code quality gate: PASS for the 0.4.16 source proxy host-port matching repair scope
- Production release gate: partial for 0.4.x macOS internal update history; No-Go for full cross-platform production until `ctrip` real-site DevLink + ZIP E2E evidence, Windows real-machine signing/install/self-update evidence, Git tag / GitHub release assets, and formal delivery batch are closed
