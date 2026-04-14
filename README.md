# crawler4j Monorepo

`crawler4j` 现在按 `uv` workspace 的 monorepo 组织。仓库根目录只负责开发编排、统一锁文件、文档和发布动作，真正的可发布项目全部位于 `packages/`。

## Workspace Layout

```text
crawler4j/
├── packages/
│   ├── crawler4j/            # 桌面应用与 Core 运行时
│   ├── crawler4j-sdk/        # SDK 与 CLI
│   └── crawler4j-contracts/  # Core / SDK 共享契约
├── scripts/                  # workspace 级开发/验证脚本
├── docs/                     # 正式文档
├── .factory/                 # 工厂记忆与工作项
├── pyproject.toml            # workspace 开发环境
└── uv.lock                   # 全仓统一锁文件
```

## Common Commands

```bash
# 同步整个 workspace（默认包含 dev 组）
uv sync --all-packages

# 启动桌面应用
uv run python -m src.ui.app

# 运行主程序自动化测试
uv run pytest packages/crawler4j/tests -q

# 运行默认 lint
uv run ruff check .

# UI smoke
uv run python scripts/smoke_test_ui.py

# 构建三个包
uv build --package crawler4j --out-dir /tmp/crawler4j-build-check
uv build --package crawler4j-sdk --out-dir /tmp/crawler4j-sdk-build-check
uv build --package crawler4j-contracts --out-dir /tmp/crawler4j-contracts-build-check

# PyInstaller 打包桌面应用
uv run pyinstaller packages/crawler4j/crawler4j.spec
```

## Packages

- `packages/crawler4j`: 桌面应用、Core 运行时、内置模块与打包脚本
- `packages/crawler4j-sdk`: 模块开发 SDK 与 `crawler4j` CLI
- `packages/crawler4j-contracts`: Core / SDK 共用的稳定契约
- `scripts/`: workspace 级维护脚本，例如 UI smoke、数据库初始化、图标生成和历史调试辅助

详细背景和操作说明以仓库根目录 `docs/` 为准。
