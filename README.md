# crawler4j Monorepo

`crawler4j` 现在按 `uv` workspace 的 monorepo 组织。仓库根目录只负责开发编排、统一锁文件、文档和发布收口；真正可发布的代码包位于 `packages/`。

## Release Baseline

当前源码版本线已收敛为 `crawler4j 0.2.0`、`crawler4j-sdk 0.3.0`、`crawler4j-contracts 0.2.0`，但最近一次正式 Git tag 仍是 `v0.1.1`。发布前请同时区分“当前源码版本”和“最近正式发布”：

| 对象 | 当前值 | 说明 |
|---|---|---|
| `crawler4j-workspace` | `0.0.0` | workspace 开发元包，不作为正式发布物 |
| `crawler4j` | `0.2.0` | 桌面宿主与 Core 运行时包 |
| `crawler4j-sdk` | `0.3.0` | 模块开发 SDK 与 CLI |
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

# 清空各自 dist 后统一构建三个包
uv run build

# 只构建一个包，但仍然落到该包自己的 dist/
uv run build crawler4j

# 直接按包名发布 SDK / Contracts（脚本会自动指向各自 dist/*）
uv run publish crawler4j-sdk
uv run publish crawler4j-contracts

# 固定目录打包桌面应用
uv run package-desktop

# macOS 内部 DMG + Sparkle 发布
uv run install-sparkle --archive ~/Downloads/Sparkle-2.x.y.tar.xz

cp .env.example .env

CRAWLER4J_SPARKLE_ROOT=/path/to/sparkle \
CRAWLER4J_SPARKLE_FEED_URL=https://updates.example.com/crawler4j/appcast.xml \
CRAWLER4J_SPARKLE_PUBLIC_ED_KEY=<sparkle-public-key> \
uv run package-macos-internal-release

CRAWLER4J_SPARKLE_FEED_URL=https://updates.example.com/crawler4j/appcast.xml \
CRAWLER4J_SPARKLE_PUBLIC_ED_KEY=<sparkle-public-key> \
CRAWLER4J_UPDATE_UPLOAD_TARGET=deploy@example.internal:/srv/nginx/updates/crawler4j/ \
uv run deploy-macos-internal-release
```

桌面打包固定输出：

- 发布产物：`packages/crawler4j/dist/desktop/<platform>/`
- PyInstaller 中间构建目录：`packages/crawler4j/build/pyinstaller/<platform>/`
- macOS 最终分发物：`packages/crawler4j/dist/desktop/macos/Crawler4j.app`
- macOS 内部 Sparkle 更新产物：`packages/crawler4j/dist/updates/macos/`

其中 `build/pyinstaller/...` 只保存 PyInstaller 的分析缓存与中间文件，不是发布物；需要精简工作区时可以删除，下一次 `uv run package-desktop` 会自动重建。macOS 打包完成后，脚本会自动删除 PyInstaller 旁路生成的松散 `Crawler4j/` collect 目录，避免把非分发目录误当成必须随包携带的正式产物。

若需要给小范围内部用户分发带自动更新能力的 macOS 包，继续以 `PyInstaller -> Crawler4j.app` 为底座，再通过 `uv run package-macos-internal-release` 把 `Sparkle.framework`、`SUFeedURL` / `SUPublicEDKey`、DMG 与 `appcast.xml` 串起来。当前生成的 DMG 会固定成 `Crawler4j.app + Applications` 的拖拽安装视图；打包脚本还会把 `SUEnableCodeSigningValidation=false` 和空的 `SUPackageSigningCertificate` 写进 `Info.plist`，仅关闭宿主 app 的苹果代码签名校验，更新包仍继续依赖 `SUPublicEDKey` 做 EdDSA 校验。该路径面向“首次手动拖到 `/Applications` 并允许未知开发者”场景，不要求 `Developer ID` / notarization。
若本机尚未放置 Sparkle 分发目录，可先下载 Sparkle 官方 release archive，再运行 `uv run install-sparkle --archive /path/to/Sparkle-*.tar.xz` 把 `Sparkle.framework` 与 `bin/generate_appcast` 解压到仓库约定的 `packages/crawler4j/vendor/macos/sparkle/`。发布脚本现在会默认读取 workspace 根的 `.env`；仓库提供了 `.env.example` 模板，可先复制成 `.env` 再填 `CRAWLER4J_SPARKLE_FEED_URL`、`CRAWLER4J_SPARKLE_PUBLIC_ED_KEY`、`CRAWLER4J_UPDATE_UPLOAD_TARGET`。若要一键打包并推送到 nginx 静态目录，则使用 `uv run deploy-macos-internal-release`，它会先复用现有 DMG/appcast 构建链，再通过 `rsync -av` 把 `packages/crawler4j/dist/updates/macos/` 下的产物同步到 `CRAWLER4J_UPDATE_UPLOAD_TARGET` 指定的本地目录或 `user@host:/path/` 目标。服务器端 nginx / 证书样板见 `deploy/nginx/crawler4j-updates.example.conf`，默认推荐把更新子域名固定为 `updates.<主域名>`。

## Packages

- `packages/crawler4j`: 桌面宿主、Core 运行时与 PyInstaller 打包规格
- `packages/crawler4j-sdk`: 模块开发 SDK 与 `crawler4j` CLI
- `packages/crawler4j-contracts`: Core / SDK / 模块共用的稳定契约
- `scripts/`: workspace 级维护脚本，当前保留统一构建、UI smoke 与数据库初始化/重置辅助

当前保留的脚本：

- `scripts/build_workspace_packages.py`：`uv run build` / `uv run publish` 背后的统一包装器；构建时自动写回各包 `dist/`，发布时自动指向各包 `dist/*`
- `scripts/deploy_macos_internal_release.py`：`uv run deploy-macos-internal-release` 背后的 macOS 内部发布+上传入口；复用 `package-macos-internal-release` 构建 DMG / `appcast.xml`，再用 `rsync` 上传到 `CRAWLER4J_UPDATE_UPLOAD_TARGET`
- `scripts/install_sparkle_vendor.py`：`uv run install-sparkle` 背后的 Sparkle 安装辅助；把本地下载好的 Sparkle release archive 或已解压目录复制到 `packages/crawler4j/vendor/macos/sparkle/`
- `scripts/package_desktop_app.py`：`uv run package-desktop` 背后的固定目录桌面打包入口；输出固定落在 `packages/crawler4j/dist/desktop/<platform>/`，其中 macOS 只保留最终可分发的 `Crawler4j.app`
- `scripts/package_macos_internal_release.py`：`uv run package-macos-internal-release` 背后的 macOS 内部发布入口；要求本机可访问 Sparkle 分发目录与 EdDSA 公钥环境变量，并在 `packages/crawler4j/dist/updates/macos/` 生成 DMG / `appcast.xml`
- `scripts/smoke_test_ui.py`：默认质量门里的 headless UI smoke
- `scripts/db_cli.py`：本地维护用数据库初始化/重置脚本

详细背景和操作说明以仓库根目录 `docs/` 为准。
