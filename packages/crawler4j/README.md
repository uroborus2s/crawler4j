# crawler4j

`crawler4j` 是 monorepo 中的桌面宿主与 Core 运行时包，当前源码版本基线为 `0.2.0`。

它负责承载桌面 Shell、ATM / REM / MMS 等运行时能力，以及版本读取、调试桥接和 PyInstaller 打包。

## Package Layout

- `src/`: 桌面应用与运行时源码
- `tests/`: 宿主侧单元 / 集成测试
- `crawler4j.spec`: PyInstaller 打包规格
- `pyproject.toml`: 包元数据、依赖与入口定义

workspace 级开发脚本已经统一迁到仓库根 `scripts/`，不再作为 `packages/crawler4j` 的目录内容。当前保留：

- `scripts/build_workspace_packages.py`：清空各包 `dist/` 后统一执行 `uv build --package ... --out-dir ... --clear`
- `scripts/smoke_test_ui.py`：默认质量门里的 headless UI smoke
- `scripts/db_cli.py`：本地维护用数据库初始化/重置脚本

## 从 workspace 根目录开发

```bash
uv sync --all-packages
uv run python -m src.ui.app
uv run pytest -q
uv run python scripts/smoke_test_ui.py
uv run python scripts/build_workspace_packages.py
uv run pyinstaller packages/crawler4j/crawler4j.spec
```

如果单独安装本包，会暴露 `start` 入口；在 monorepo 工作区内仍统一使用 `uv run python -m src.ui.app`。

正式说明、开发流程和发布规范以仓库根目录的 `docs/` 为准。
