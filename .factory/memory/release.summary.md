# Release Summary

- Latest formal release tag: `v0.2.0` on 2026-04-20
- Current workspace root version: `0.0.0`
- Current app package version: `0.4.39`
- Runtime package version: `0.4.39`
- SDK release candidate: `0.4.5` (publish pending)
- Contracts release candidate: `0.4.4` (publish pending)

Evidence status:

- Root build: `crawler4j 0.4.39` wheel/sdist built on 2026-07-15; wheel METADATA and embedded package README report `0.4.39`
- Desktop PyInstaller / macOS Sparkle bundle: passed on 2026-06-19 for `crawler4j 0.4.16`; old remote `Crawler4j-0.4.16.dmg` was removed, new `Crawler4j-0.4.16.dmg` / `appcast.xml` were generated and uploaded, public DMG `HEAD 200`, SHA256 `8463f4982ea4948a2151a7061449fc8a3fd9152848b37197a35504efb1f04243`
- SDK build/publish: `crawler4j-sdk 0.4.5` wheel/sdist built; dependency is `crawler4j-contracts>=0.4.4,<0.5.0`; publish dry-run passed
- Contracts build/publish: `crawler4j-contracts 0.4.4` wheel/sdist built; publish dry-run passed
- Full test/lint gate: 2026-07-15 full unit `1235 passed` plus 13 known environment-baseline failures; focused `175 passed`; root sdist contamination TDD and manifest gate passed; full Ruff, lock, JSON, docs-stratego, UI smoke and diff checks passed
- UI / CLI smoke: client UI smoke passed on 2026-07-15; historical SDK CLI help remains passed
- Docs validate: passed on 2026-07-15 with `pages=87 contracts=0`

Release decision:

- Contracts / SDK pre-publish gate: PASS for Contracts 0.4.4 / SDK 0.4.5; formal upload and online verification pending
- Client source version gate: PASS for crawler4j 0.4.39; desktop installer build/upload not included
- Production release gate: partial for 0.4.x macOS internal update history; No-Go for full cross-platform production until `ctrip` real-site DevLink + ZIP E2E evidence, Windows real-machine signing/install/self-update evidence, Git tag / GitHub release assets, and formal delivery batch are closed
