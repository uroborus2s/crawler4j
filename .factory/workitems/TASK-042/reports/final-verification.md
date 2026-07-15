# TASK-042 Final Release Verification

- Actor: `/root`
- Date: 2026-07-15
- Verification claim: Contracts 0.4.4 / SDK 0.4.5 are correctly published, client/root 0.4.39 source artifacts are valid, and the branch is ready for final evidence commit and remote push.
- Conclusion: `passed_for_release_and_push`

## Fresh commands and results

- Release-focused six-file pytest command: exit `0`, `175 passed`, `0 failed`, `0 errors`, `0 skipped`.
- Packaging configuration file: exit `0`, `63 passed`; both sdist-contamination RED/GREEN cycles are recorded separately.
- Full unit after the fix: `1235 passed`, `13 failed`; failures are the same 5 sandbox debug-session path and 8 read-only REM/proxy database environment baselines, with no changed-scope failure.
- `uv run ruff check .`: exit `0`, all checks passed.
- `uv lock --check`: exit `0`, 78 packages resolved.
- `.factory/project.json` JSON validation: exit `0`.
- UI smoke: exit `0`, Shell structure and Dashboard async refresh verified.
- docs-stratego: exit `0`, `pages=87 contracts=0`.
- `git diff --check`: exit `0`.

## Artifact and publication checks

- Root 0.4.39 wheel/sdist build: exit `0`; sdist is 37,279,993 bytes / 529 entries and contains no preserved desktop, updates or temporary subtree.
- Contracts 0.4.4 publish: exit `0`; PyPI returned two files whose SHA256 match local artifacts.
- SDK 0.4.5 publish: exit `0`; PyPI returned two files whose SHA256 match local artifacts; online dependency is `crawler4j-contracts<0.5.0,>=0.4.4`.
- Isolated install from PyPI: exit `0`; metadata/imports report Contracts 0.4.4 and SDK 0.4.5 from isolated `site-packages`, not workspace editable sources.
- Independent release candidate rereview: `approved`, score `100/100`, no unresolved findings.

## Requirement check

- Required upgrades: complete for root/client 0.4.39, Contracts 0.4.4 and SDK 0.4.5.
- PyPI publication: complete for the two existing package projects; no new root PyPI project was created.
- Consumer module boundary: no consumer module was modified.
- Desktop/tag/GitHub Release boundary: not run because the user requested package/client source upgrades and repository push, not new desktop release assets.
- Remote branch delivery: pending the final evidence commit and `git push origin 0.4.0`; must be verified before the user-facing completion statement.
