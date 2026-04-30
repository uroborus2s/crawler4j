# Release Summary

- Latest formal release tag: `v0.2.0` on 2026-04-20
- Current workspace root version: `0.0.0`
- Current app package version: `0.4.0`
- Runtime package version: `0.4.0`
- SDK version: `0.4.0`
- Contracts version: `0.4.0`

Evidence status:

- Root build: pending for current `crawler4j 0.4.0`; 2026-04-29 `crawler4j-0.3.2` evidence is historical
- Desktop PyInstaller bundle: historical pass on 2026-04-24 before the QScintilla dependency line; current QScintilla package/bundle evidence is pending
- SDK build/publish: pending for current `crawler4j-sdk 0.4.0`; historical `0.5.x/0.6.x` evidence is not current release evidence
- Contracts build/publish: pending for current `crawler4j-contracts 0.4.0`; historical `0.3.0` evidence is not current release evidence
- Full test/lint gate: not rerun for the whole workspace in this SDK / Contracts 0.4.0 upgrade turn; focused SDK/Core/integration gates are recorded in `tests.summary.md`
- Docs validate: not rerun in this documentation-memory sync turn
