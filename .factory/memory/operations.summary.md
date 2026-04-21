# Operations Summary

Recommended commands:

```bash
uv sync --all-packages
uv run pytest -q
uv run python -m src.ui.app
uv run python scripts/smoke_test_ui.py
uv run package-desktop
uv run package-macos-internal-release
CRAWLER4J_VELOPACK_FEED_URL=https://updates.example.com/crawler4j/win/releases.win.json uv run package-windows-release
```

Workspace root no longer relies on `uv run start`; the supported launch path is `uv run python -m src.ui.app`.
Windows 正式发布当前收口为 `PyInstaller onedir + Velopack`，更新产物固定输出到 `packages/crawler4j/dist/updates/windows/`。
