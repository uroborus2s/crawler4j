# TASK-042 Release Candidate Review Response

## Important: contaminated root sdist

Resolved at the root cause:

- `scripts/build_workspace_packages.py` preserves desktop output outside the Hatch package root.
- A post-build manifest gate rejects any root sdist containing preserved `desktop` content.
- Two regression checks were observed RED before implementation and GREEN after it.
- Root 0.4.39 was rebuilt: sdist reduced from about 177 MiB / 2,186 temporary bundle entries to 37,279,993 bytes / 529 expected source entries, with no desktop or temporary subtree.
- Hash and release evidence were refreshed.

## Minor: docs count

Release notes now use the fresh docs-stratego result `pages=87 contracts=0`.

## Minor: reproducible focused test

Release evidence now includes the exact six-file pytest command, exit code and result `175 passed`.

## Verification

See `.factory/workitems/TASK-042/evidence/root-sdist-contamination-fix-tdd.md` and the refreshed release evidence.
