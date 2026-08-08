# Release Summary

- Latest formal release tag: `v0.2.0` on 2026-04-20
- Current workspace root version: `0.0.0`
- Current app package version: `0.4.41`
- Runtime package version: `0.4.41`
- SDK source / published version: `0.4.6`
- Contracts source / published version: `0.4.5`

Evidence status:

- Published packages: Contracts `0.4.5` then SDK `0.4.6` uploaded to PyPI on 2026-08-08; online wheel/sdist SHA-256, SDK Contracts dependency metadata and fresh PyPI installation passed.
- Root current build: `crawler4j 0.4.41` wheel/sdist built on 2026-08-08; complete isolated install and desktop packaging were not run for this version.
- Root build: `crawler4j 0.4.40` wheel/sdist built on 2026-07-19; METADATA contains `httpx[brotli,http2]>=0.28.1`; isolated install auto-installed h2/hpack/hyperframe/brotli and passed the runtime/tool smoke
- Desktop PyInstaller: macOS arm64 0.4.40 validation app built on 2026-07-19; after fixing missing distribution metadata collection, frozen `--crawler4j-verify-http-runtime` returned `http2_client=ok`. Signed DMG/update asset not produced.
- SDK historical release: `crawler4j-sdk 0.4.5` wheel/sdist published after Contracts; online hashes and dependency metadata match, isolated PyPI install passed
- Contracts historical release: `crawler4j-contracts 0.4.4` wheel/sdist published first; online hashes match local artifacts and isolated install passed
- Full test/lint gate: 2026-08-08 full unit `1287 passed`; CR-025 focused functionality and packaging `320 passed`; integration/acceptance `32 passed`; full Ruff, lock, JSON, docs-stratego and diff checks passed
- UI / CLI smoke: client UI smoke passed on 2026-07-15; historical SDK CLI help remains passed
- Docs validate: passed on 2026-08-08 with `pages=87 contracts=0`

Release decision:

- Contracts / SDK release gate: PASS for Contracts 0.4.5 / SDK 0.4.6
- Client source/runtime gate: crawler4j 0.4.41 source and wheel/sdist build pass in CR-025; isolated wheel and macOS frozen app evidence remains at 0.4.40, so 0.4.41 desktop publication is not authorized in this task
- Production release gate: No-Go until external `ctrip_crawler` migrates to host `http.request` and passes DevLink + ZIP real-site E2E, Windows runtime/signing/install/self-update evidence, signed desktop assets, Git tag / GitHub release assets, and formal delivery batch are closed
