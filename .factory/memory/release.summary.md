# Release Summary

- Latest formal release tag: `v0.2.0` on 2026-04-20
- Current workspace root version: `0.0.0`
- Current app package version: `0.4.2`
- Runtime package version: `0.4.2`
- SDK version: `0.4.1`
- Contracts version: `0.4.1`

Evidence status:

- Root build: pending for current `crawler4j 0.4.2`; 0.4.1 wheel/sdist evidence remains historical
- Desktop PyInstaller / macOS Sparkle bundle: passed on 2026-05-18 for 0.4.1; `uv run deploy-macos-internal-release` generated `Crawler4j.app`, `Crawler4j-0.4.1.dmg`, `appcast.xml`, and uploaded the macOS update directory; 0.4.2 client bundles still need a fresh build
- SDK build/publish: passed on 2026-05-18 for current `crawler4j-sdk 0.4.1`; wheel/sdist uploaded to PyPI
- Contracts build/publish: passed on 2026-05-18 for current `crawler4j-contracts 0.4.1`; wheel/sdist uploaded to PyPI
- Full test/lint gate: passed on 2026-05-18 for the 0.4.2 root version bump; `uv run pytest -q -p no:cacheprovider` => `992 passed`, `uv run ruff check .`, `uv lock --check`, `jq empty .factory/project.json`, and `git diff --check` passed
- UI / CLI smoke: passed on 2026-05-01; `uv run python scripts/smoke_test_ui.py` and `uv run python -m crawler4j_sdk.cli.commands --help` passed
- Docs validate: not rerun in this documentation-memory sync turn

Release decision:

- Local code quality gate: PASS for the 0.4.2 root version bump scope
- Production release gate: No-Go until `ctrip` real-site DevLink + ZIP E2E evidence, Windows real-machine signing/install/self-update evidence, Git tag / GitHub release assets, and formal delivery batch are closed
