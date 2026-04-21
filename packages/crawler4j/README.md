# crawler4j

`crawler4j` 是 monorepo 中的桌面宿主与 Core 运行时包，当前源码版本基线为 `0.2.0`。

它负责承载桌面 Shell、ATM / REM / MMS 等运行时能力，以及版本读取、调试桥接和 PyInstaller 打包。

## Package Layout

- `src/`: 桌面应用与运行时源码
- `tests/`: 宿主侧单元 / 集成测试
- `crawler4j.spec`: PyInstaller 打包规格
- `pyproject.toml`: 包元数据、依赖与入口定义

workspace 级开发脚本已经统一迁到仓库根 `scripts/`，不再作为 `packages/crawler4j` 的目录内容。当前保留：

- `scripts/build_workspace_packages.py`：`uv run build` / `uv run publish` 背后的统一包装器；构建时自动写回各包 `dist/`，发布时自动指向各包 `dist/*`
- `scripts/smoke_test_ui.py`：默认质量门里的 headless UI smoke
- `scripts/db_cli.py`：本地维护用数据库初始化/重置脚本

## 从 workspace 根目录开发

```bash
uv sync --all-packages
uv run python -m src.ui.app
uv run pytest -q
uv run python scripts/smoke_test_ui.py
uv run build
uv run package-desktop
CRAWLER4J_SPARKLE_ROOT=/path/to/sparkle \
CRAWLER4J_SPARKLE_FEED_URL=https://example.internal/crawler4j/appcast.xml \
CRAWLER4J_SPARKLE_PUBLIC_ED_KEY=<sparkle-public-key> \
uv run package-macos-internal-release
UV_PUBLISH_TOKEN=<your-token> uv run publish crawler4j-sdk
```

如果单独安装本包，会暴露 `start` 入口；在 monorepo 工作区内仍统一使用 `uv run python -m src.ui.app`。桌面打包统一走 workspace 根的 `uv run package-desktop`；当前 macOS 最终可分发产物是 `packages/crawler4j/dist/desktop/macos/Crawler4j.app`，不需要再额外携带旁边的 PyInstaller collect 目录。若要做小范围内部 DMG 分发并让后续更新交给 Sparkle，则在 base app 构建完成后继续执行 `uv run package-macos-internal-release`，它会在 `packages/crawler4j/dist/updates/macos/` 生成内部用 DMG / `appcast.xml`。

正式说明、开发流程和发布规范以仓库根目录的 `docs/` 为准。
