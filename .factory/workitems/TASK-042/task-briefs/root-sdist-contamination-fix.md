# TASK-042 Root sdist Contamination Fix

- Root cause: confirmed in `../evidence/root-sdist-contamination-investigation.md`
- User confirmation: 2026-07-15 request to proceed immediately with upgrades, PyPI publication and remote push after the blocker was explained

## Fix

- Move desktop-artifact preservation outside the Hatch package root while root wheel/sdist is built.
- Add a regression that observes the build boundary and proves no preservation directory exists inside the package root.
- Add a post-build root sdist content gate that rejects any preserved `desktop` subtree.
- Rebuild root 0.4.39, refresh hashes/evidence and re-run independent review.

## Boundaries

- Do not change desktop packaging output semantics.
- Do not publish root `crawler4j` to PyPI.
- Do not modify consumer modules or add business behavior.
