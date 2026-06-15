# crawler4j Monorepo

`crawler4j` 现在按 `uv` workspace 的 monorepo 组织。仓库根目录只负责开发编排、统一锁文件、文档和发布收口；真正可发布的代码包位于 `packages/`。

## Release Baseline

当前源码版本线已收敛为 `crawler4j 0.4.14`、`crawler4j-sdk 0.4.2`、`crawler4j-contracts 0.4.2`，最近一次正式 Git tag 为 `v0.2.0`。发布前请同时区分“当前源码版本”和“最近正式发布”：

| 对象 | 当前值 | 说明 |
|---|---|---|
| `crawler4j-workspace` | `0.0.0` | workspace 开发元包，不作为正式发布物 |
| `crawler4j` | `0.4.14` | 桌面宿主与 Core 运行时包 |
| `crawler4j-sdk` | `0.4.2` | 模块开发 SDK 与 CLI |
| `crawler4j-contracts` | `0.4.2` | Core / SDK / 模块共享契约 |
| 最近正式 Git tag | `v0.2.0` | 仓库中最新已知正式 tag |

当前版本线不等于已经完成正式 tag / GitHub release。`crawler4j 0.4.14` 推进桌面宿主与 Core 运行时包版本，用于在环境管理列表展示环境绑定的代理 IP，并承接此前已有环境导入 workflow 契约、`env.get_proxy` 当前代理读取和多环境导入批次元数据；`crawler4j-sdk 0.4.2`、`crawler4j-contracts 0.4.2` 用于对外发布这批 SDK/Contracts 契约。当前最新已记录 macOS Sparkle 客户端升级包仍为 2026-05-26 生成并上传的 `0.4.3`；`0.4.14` 客户端包、`ctrip` 真实站点 E2E、Windows 真机安装/升级证据、Git tag / GitHub release 与正式交付批次仍需继续收口。

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

# 直接按包名发布 workspace 包时，按依赖顺序先发 contracts，再发 sdk
uv run publish crawler4j-contracts
uv run publish crawler4j-sdk

# 固定目录打包桌面应用
uv run package-desktop

# macOS 内部 DMG + Sparkle 发布
uv run install-sparkle --archive ~/Downloads/Sparkle-2.x.y.tar.xz

cp .env.example .env

CRAWLER4J_SPARKLE_ROOT=/path/to/sparkle \
CRAWLER4J_SPARKLE_FEED_URL=https://updates.example.com/mac/appcast.xml \
CRAWLER4J_SPARKLE_PUBLIC_ED_KEY=<sparkle-public-key> \
CRAWLER4J_SPARKLE_KEYCHAIN_ACCOUNT=ed25519 \
uv run package-macos-internal-release

CRAWLER4J_SPARKLE_FEED_URL=https://updates.example.com/mac/appcast.xml \
CRAWLER4J_SPARKLE_PUBLIC_ED_KEY=<sparkle-public-key> \
CRAWLER4J_SPARKLE_KEYCHAIN_ACCOUNT=ed25519 \
CRAWLER4J_UPDATE_UPLOAD_TARGET=deploy@example.internal:/var/www/crawler4j/ \
uv run deploy-macos-internal-release

# Windows Setup.exe + Velopack 发布
cp .env.example .env

CRAWLER4J_VELOPACK_FEED_URL=https://updates.example.com/win/releases.win.json \
uv run package-windows-release

CRAWLER4J_VELOPACK_FEED_URL=https://updates.example.com/win/releases.win.json \
CRAWLER4J_UPDATE_UPLOAD_TARGET=deploy@example.internal:/var/www/crawler4j/ \
uv run deploy-windows-release
```

桌面打包固定输出：

- 发布产物：`packages/crawler4j/dist/desktop/<platform>/`
- PyInstaller 中间构建目录：`packages/crawler4j/build/pyinstaller/<platform>/`
- macOS 最终分发物：`packages/crawler4j/dist/desktop/macos/Crawler4j.app`
- macOS 内部 Sparkle 更新产物：`packages/crawler4j/dist/updates/macos/`
- Windows Velopack 更新产物：`packages/crawler4j/dist/updates/windows/`

其中 `build/pyinstaller/...` 只保存 PyInstaller 的分析缓存与中间文件，不是发布物；需要精简工作区时可以删除，下一次 `uv run package-desktop` 会自动重建。macOS 打包完成后，脚本会自动删除 PyInstaller 旁路生成的松散 `Crawler4j/` collect 目录，避免把非分发目录误当成必须随包携带的正式产物。
桌面壳层图标的母版固定为 `packages/crawler4j/src/ui/assets/app_icon_master.png`；如需继续微调 Dock 占比或品牌细节，统一执行 `uv run python scripts/rebuild_app_icon_assets.py` 重建 `app_icon.png`、`app_icon.icns` 与 `app_icon.ico`，不要分别手工改三套导出物。

若需要给小范围内部用户分发带自动更新能力的 macOS 包，继续以 `PyInstaller -> Crawler4j.app` 为底座，再通过 `uv run package-macos-internal-release` 把 `Sparkle.framework`、`SUFeedURL` / `SUPublicEDKey`、DMG 与 `appcast.xml` 串起来。当前生成的 DMG 会固定成 `Crawler4j.app + Applications` 的拖拽安装视图；打包脚本还会把 `SUEnableCodeSigningValidation=false` 和空的 `SUPackageSigningCertificate` 写进 `Info.plist`，并在生成 DMG 前自动对改写后的 bundle 做一次 ad-hoc 重签，仅关闭宿主 app 的苹果代码签名校验，更新包仍继续依赖 EdDSA 校验。该路径面向“首次手动拖到 `/Applications` 并允许未知开发者”场景，不要求 `Developer ID` / notarization。
若本机尚未放置 Sparkle 分发目录，可先下载 Sparkle 官方 release archive，再运行 `uv run install-sparkle --archive /path/to/Sparkle-*.tar.xz` 把 `Sparkle.framework` 与 `bin/generate_appcast` 解压到仓库约定的 `packages/crawler4j/vendor/macos/sparkle/`。发布脚本现在会默认读取 workspace 根的 `.env`；仓库提供了 `.env.example` 模板，可先复制成 `.env` 再填 `CRAWLER4J_SPARKLE_FEED_URL`、`CRAWLER4J_SPARKLE_PUBLIC_ED_KEY`，以及一条私钥来源配置：`CRAWLER4J_SPARKLE_KEYCHAIN_ACCOUNT`、`CRAWLER4J_SPARKLE_PRIVATE_ED_KEY_FILE` 或 `CRAWLER4J_SPARKLE_PRIVATE_ED_KEY` 三选一。若要一键打包并推送到静态目录，则使用 `uv run deploy-macos-internal-release`，它会先复用现有 DMG/appcast 构建链，再通过 `rsync -av` 把 `packages/crawler4j/dist/updates/macos/` 下的产物同步到 `CRAWLER4J_UPDATE_UPLOAD_TARGET/mac/`。服务器目录建议固定为同一发布根下的 `mac/` 与 `win/` 两个并列子目录。
若需要给 Windows 正式用户分发安装器并让宿主自己完成后续升级，则继续以 `PyInstaller onedir` 作为底座，再执行 `uv run package-windows-release`。该脚本会默认读取 workspace 根的 `.env`，把 `CRAWLER4J_VELOPACK_FEED_URL`、可选的 `CRAWLER4J_VELOPACK_PACK_ID` / `CRAWLER4J_VELOPACK_CHANNEL` / `CRAWLER4J_VELOPACK_RUNTIME` 写入宿主 bundle 内的 `crawler4j.update.json`，随后调用 `vpk pack`（或在设置 `CRAWLER4J_VPK_USE_DNX=1` 时调用 `dnx vpk`）生成 `Setup.exe`、`.nupkg` 与 `releases.<channel>.json`。Windows 上若 `dnx` / `vpk` 实际落成 `*.cmd` 或 `*.bat` shim，脚本现在会自动改用 `cmd.exe /c` 启动；若当前 Python `velopack` 包版本带 `.dev` / `+local` 后缀，脚本也会先把它正规化成 NuGet 可接受的基础版本后再传给 `dnx --version`，避免继续命中 `invalid NuGet version`。若需要同步到服务器，再执行 `uv run deploy-windows-release`，它会通过系统自带的 OpenSSH `sftp` 把 `packages/crawler4j/dist/updates/windows/` 下的产物上传到 `CRAWLER4J_UPDATE_UPLOAD_TARGET/win/`，不再要求额外安装 `rsync`。Windows 端正式交付建议始终让用户先运行 `Setup.exe`，不要直接把程序装进 `Program Files`；首次安装完成后，后续可通过 `系统设置 -> 关于 -> 检查更新` 走 Velopack 的下载并重启升级链路。

## Packages

- `packages/crawler4j`: 桌面宿主、Core 运行时与 PyInstaller 打包规格
- `packages/crawler4j-sdk`: 模块开发 SDK 与 `crawler4j` CLI
- `packages/crawler4j-contracts`: Core / SDK / 模块共用的稳定契约
- `scripts/`: workspace 级维护脚本，当前保留统一构建、UI smoke 与数据库初始化/重置辅助

当前保留的脚本：

- `scripts/build_workspace_packages.py`：`uv run build` / `uv run publish` 背后的统一包装器；按 `crawler4j-contracts -> crawler4j-sdk -> crawler4j` 的依赖顺序构建/发布，并自动写回各包 `dist/`
- `scripts/deploy_macos_internal_release.py`：`uv run deploy-macos-internal-release` 背后的 macOS 内部发布+上传入口；复用 `package-macos-internal-release` 构建 DMG / `appcast.xml`，再用 `rsync` 上传到 `CRAWLER4J_UPDATE_UPLOAD_TARGET/mac/`
- `scripts/deploy_windows_release.py`：`uv run deploy-windows-release` 背后的 Windows 发布+上传入口；复用 `package-windows-release` 生成 Velopack 产物，再用 OpenSSH `sftp` 上传到 `CRAWLER4J_UPDATE_UPLOAD_TARGET/win/`
- `scripts/install_sparkle_vendor.py`：`uv run install-sparkle` 背后的 Sparkle 安装辅助；把本地下载好的 Sparkle release archive 或已解压目录复制到 `packages/crawler4j/vendor/macos/sparkle/`
- `scripts/package_desktop_app.py`：`uv run package-desktop` 背后的固定目录桌面打包入口；输出固定落在 `packages/crawler4j/dist/desktop/<platform>/`，其中 macOS 只保留最终可分发的 `Crawler4j.app`
- `scripts/package_macos_internal_release.py`：`uv run package-macos-internal-release` 背后的 macOS 内部发布入口；要求本机可访问 Sparkle 分发目录、EdDSA 公钥与一条私钥来源配置，并在 `packages/crawler4j/dist/updates/macos/` 生成 DMG / `appcast.xml`
- `scripts/package_windows_release.py`：`uv run package-windows-release` 背后的 Windows 发布入口；复用 `PyInstaller onedir` 目录，写入 Velopack 更新配置并生成 `Setup.exe` / `.nupkg` / `releases.<channel>.json`
- `scripts/rebuild_app_icon_assets.py`：从 `packages/crawler4j/src/ui/assets/app_icon_master.png` 重建运行时 PNG、macOS ICNS 和 Windows ICO，统一控制 Dock 外轮廓安全区
- `scripts/smoke_test_ui.py`：默认质量门里的 headless UI smoke
- `scripts/db_cli.py`：本地维护用 `config.db` / `state.db` / `data.db` 初始化与全量重置脚本

详细背景和操作说明以仓库根目录 `docs/` 为准。
