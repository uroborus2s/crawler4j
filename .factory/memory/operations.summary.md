# Operations Summary

Recommended commands:

```bash
uv sync --all-packages
uv run pytest -q
uv run python -m src.ui.app
uv run python scripts/smoke_test_ui.py
uv run package-desktop
CRAWLER4J_SPARKLE_FEED_URL=https://updates.example.com/mac/appcast.xml uv run package-macos-internal-release
CRAWLER4J_UPDATE_UPLOAD_TARGET=deploy@example.internal:/var/www/crawler4j/ uv run deploy-macos-internal-release
CRAWLER4J_VELOPACK_FEED_URL=https://updates.example.com/win/releases.win.json uv run package-windows-release
CRAWLER4J_UPDATE_UPLOAD_TARGET=deploy@example.internal:/var/www/crawler4j/ uv run deploy-windows-release
```

Workspace root no longer relies on `uv run start`; the supported launch path is `uv run python -m src.ui.app`.
Windows 正式发布当前收口为 `PyInstaller onedir + Velopack`，更新产物固定输出到 `packages/crawler4j/dist/updates/windows/`。
`CRAWLER4J_UPDATE_UPLOAD_TARGET` 现在表示公共发布根目录；macOS / Windows 上传脚本会分别追加 `mac/` 与 `win/` 子目录。
