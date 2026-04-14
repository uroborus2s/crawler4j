# crawler4j

`crawler4j` 是 monorepo 中的桌面应用与 Core 运行时包，包含：

- `src/`: 桌面应用与运行时源码
- `modules/`: 跟随宿主分发的内置模块资产
- `crawler4j.spec`: PyInstaller 打包规格

workspace 级开发脚本已经统一迁到仓库根 `scripts/`，不再作为 `packages/crawler4j` 的目录内容。

## 从 workspace 根目录开发

```bash
uv sync --all-packages
uv run python -m src.ui.app
uv run pytest packages/crawler4j/tests -q
uv run python scripts/smoke_test_ui.py
uv build --package crawler4j --out-dir /tmp/crawler4j-build-check
uv run pyinstaller packages/crawler4j/crawler4j.spec
```

正式说明、开发流程和发布规范以仓库根目录的 `docs/` 为准。
