# TASK-042 Root sdist Contamination Investigation

- Date: 2026-07-15
- Status: `root_cause_found`
- Scope: root/client build artifact only; Contracts and SDK artifacts are unaffected

## Reproduction

The independent reviewer inspected `packages/crawler4j/dist/crawler4j-0.4.39.tar.gz` and found:

- compressed size: approximately 177 MiB (`du -sh`), versus a 940 KiB wheel;
- 2,186 entries under `crawler4j-0.4.39/tmpk16q5yre/`;
- the temporary subtree contains `desktop/macos/Crawler4j.app` and bundled Qt/Python dylibs;
- the current preserved desktop directory is approximately 365 MiB with 2,079 files;
- Contracts and SDK sdists remain small and their metadata/hashes independently match the release evidence.

## Trace

1. Root builds use `scripts.build_workspace_packages.run_build()`.
2. Root target declares `PRESERVED_DIST_SUBDIRS = {"crawler4j": ("desktop",)}`.
3. `_preserve_dist_subdirs()` creates `tempfile.TemporaryDirectory(dir=target.dist_dir.parent)`.
4. For the root target, `target.dist_dir.parent` is `packages/crawler4j`, which is also the Hatch project root.
5. The helper moves `packages/crawler4j/dist/desktop` into that temporary directory before invoking `uv build`.
6. Hatch's default sdist file collection sees the temporary directory inside the project root and includes it. The wheel is not affected because the wheel target explicitly packages only `src`.
7. After build, the context manager restores `dist/desktop` and removes the temporary directory, so the source tree looks clean while the already-built sdist remains contaminated.

## Direct Cause

The root sdist includes a live build-preservation temporary directory located inside the package project root.

## Root Cause

`_preserve_dist_subdirs()` assumes a temporary directory under `target.dist_dir.parent` is invisible to package discovery. That assumption is false for Hatch sdists. The preservation mechanism and the sdist discovery boundary overlap.

## Candidate Fix Boundary

The smallest root-cause fix is to preserve `dist/desktop` in a temporary directory outside `packages/crawler4j` while the build runs. A regression should assert that root build preservation still restores desktop assets and that the root sdist contains no temporary desktop bundle or other preserved `dist` content. Release evidence/hash must then be regenerated.

No implementation change has been made as part of this investigation.
