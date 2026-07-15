# TASK-042 Root sdist Contamination Fix TDD

- Date: 2026-07-15
- Status: `passed`
- Root cause: `.factory/workitems/TASK-042/evidence/root-sdist-contamination-investigation.md`

## RED 1: preservation directory crosses the package boundary

```bash
UV_CACHE_DIR=/tmp/crawler4j-uv-cache uv run --offline --no-sync pytest packages/crawler4j/tests/unit/test_sdk/test_packaging_config.py::test_workspace_build_script_preserves_desktop_subdir_for_root_package -q -p no:cacheprovider
```

Exit `1`: the build callback observed an extra `tmpn1nxaajn` sibling inside the simulated package root.

## GREEN 1

The preservation directory now lives under the workspace root, outside `packages/crawler4j`, while desktop artifacts are still restored after build. The same test passed: `1 passed`.

## RED 2: contaminated sdist is accepted

```bash
UV_CACHE_DIR=/tmp/crawler4j-uv-cache uv run --offline --no-sync pytest packages/crawler4j/tests/unit/test_sdk/test_packaging_config.py::test_workspace_build_script_rejects_preserved_desktop_content_in_root_sdist -q -p no:cacheprovider
```

Exit `1`: `Failed: DID NOT RAISE RuntimeError` for an sdist containing `tmp-build-preserve/desktop/macos/Crawler4j.app/...`.

## GREEN 2 and regression

- Root builds now validate that exactly one sdist was produced and reject any archive member whose path contains a preserved `desktop` segment.
- Packaging regression file: `63 passed`.
- Release-focused six-file suite: `175 passed`, exit `0`.
- Fresh full unit: `1235 passed`, plus the same 13 known sandbox/read-only DB environment baselines.

## Rebuilt artifact

- Root sdist: 37,279,993 bytes, 529 entries, no `/desktop/` or `/tmp*/` subtree.
- Root sdist SHA256: `376b3e1e44ed585c1599da0f0f3a06fc3e0d95b765e5f117baff1c9f2dacc627`.
- Root wheel SHA256 remains `691d3112bc27c51f7715734bb9718cf36a4fa19185c2b7245bbf48418184fbf9`.
