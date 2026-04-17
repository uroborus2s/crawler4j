# crawler4j Monorepo

`crawler4j` 现在按 `uv` workspace 的 monorepo 组织。仓库根目录只负责开发编排、统一锁文件、文档和发布收口；真正可发布的代码包位于 `packages/`。

## Release Baseline

当前源码已经按 `0.2.0` 口径完成切版，但最近一次正式 Git tag 仍是 `v0.1.1`。发布前请同时区分“当前源码版本”和“最近正式发布”：

| 对象 | 当前值 | 说明 |
|---|---|---|
| `crawler4j-workspace` | `0.0.0` | workspace 开发元包，不作为正式发布物 |
| `crawler4j` | `0.2.0` | 桌面宿主与 Core 运行时包 |
| `crawler4j-sdk` | `0.2.0` | 模块开发 SDK 与 CLI |
| `crawler4j-contracts` | `0.2.0` | Core / SDK / 模块共享契约 |
| 最近正式 Git tag | `v0.1.1` | 仓库中最新已知正式 tag |

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

# 运行完整自动化测试
uv run pytest -q

# 只跑桌面宿主测试
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

- `packages/crawler4j`: 桌面宿主、Core 运行时与 PyInstaller 打包规格
- `packages/crawler4j-sdk`: 模块开发 SDK 与 `crawler4j` CLI
- `packages/crawler4j-contracts`: Core / SDK / 模块共用的稳定契约
- `scripts/`: workspace 级维护脚本，当前只保留 UI smoke 与数据库初始化/重置辅助

当前保留的脚本：

- `scripts/smoke_test_ui.py`：默认质量门里的 headless UI smoke
- `scripts/db_cli.py`：本地维护用数据库初始化/重置脚本

详细背景和操作说明以仓库根目录 `docs/` 为准。
