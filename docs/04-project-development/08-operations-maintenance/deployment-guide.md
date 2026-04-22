# 部署与运行说明

**项目名称：** 蛛行演略（crawler4j）
**文档状态：** 已批准
**负责人：** 当前仓库维护者
**主要读者：** 维护者 | 发布负责人 | Dev
**上游输入：** `docs/04-project-development/04-design/technical-selection.md` | 本地验证结果
**下游输出：** `docs/04-project-development/08-operations-maintenance/operations-runbook.md` | `docs/04-project-development/08-operations-maintenance/core-maintainer-guide.md` | `docs/02-user-guide/user-guide.md` | `docs/02-user-guide/admin-guide.md`
**关联 ID：** `OPS-001`, `OPS-002`, `OPS-003`, `REQ-001`, `REQ-003`, `REQ-004`
**最后更新：** 2026-04-22

## 1. 环境准备

```bash
uv sync --all-packages
```

要求：

- Python `>=3.12`
- 使用 `uv` 管理依赖与命令

## 2. 当前推荐运行方式

### 桌面应用

```bash
uv run python -m src.ui.app
```

说明：

- workspace 根通过 `uv run python -m src.ui.app` 直接启动 `packages/crawler4j` 中的真实入口
- 若需要打包，PyInstaller 规格位于 `packages/crawler4j/crawler4j.spec`
- 正式桌面打包入口统一为 `uv run package-desktop`
- 当前 macOS 最终可分发产物固定为 `packages/crawler4j/dist/desktop/macos/Crawler4j.app`，不需要再额外携带旁边的 `Crawler4j/` collect 目录
- 当前 Windows 正式发布入口固定为 `uv run package-windows-release`，它会先复用 `package-desktop` 产出的 `PyInstaller onedir` 宿主目录，再继续生成 Velopack 安装器与更新目录
- 桌面壳层图标当前统一收口为同一套 `app_icon` 资源：运行时继续使用 `app_icon.png`，macOS bundle 使用 `app_icon.icns`，Windows `Crawler4j.exe` 使用 `app_icon.ico`
- 若需要小范围内部 DMG 分发并启用 Sparkle 自动更新，使用 `uv run package-macos-internal-release`
- PyInstaller 现已显式收集 `sinanz` 的共享 `resources/` 目录；滑块验证码运行时会从其中的 `resources/models/` 解析 `slider_gap_locator.onnx`

### Windows Setup.exe + Velopack 发布

```bash
cp .env.example .env

CRAWLER4J_VELOPACK_FEED_URL=https://updates.example.com/win/releases.win.json \
uv run package-windows-release

CRAWLER4J_VELOPACK_FEED_URL=https://updates.example.com/win/releases.win.json \
CRAWLER4J_UPDATE_UPLOAD_TARGET=deploy@example.internal:/var/www/crawler4j/ \
uv run deploy-windows-release
```

说明：

- 该命令会先复用 `uv run package-desktop` 的 Windows `PyInstaller onedir` 结果，默认输入目录为 `packages/crawler4j/dist/desktop/windows/Crawler4j/`
- 随后脚本会在 onedir 根目录写入 `crawler4j.update.json`，把 Windows 宿主运行时需要的 `feed_url / pack_id / channel` 收口为同一事实源
- 默认 Velopack 输出目录为 `packages/crawler4j/dist/updates/windows/`，其中通常包含 `Setup.exe`、`releases.<channel>.json` 清单与 `.nupkg` 包
- `CRAWLER4J_VELOPACK_FEED_URL` 为必填项；正式口径建议固定为 `https://updates.example.com/win/releases.win.json`
- `CRAWLER4J_VELOPACK_PACK_ID` 默认为 `io.github.uroborus2s.crawler4j`
- `CRAWLER4J_VELOPACK_CHANNEL` 默认为 `win`
- `CRAWLER4J_VELOPACK_RUNTIME` 默认为 `win-x64`
- 若本机已全局安装 `vpk`，脚本默认直接调用它；若希望强制使用与 Python `velopack` 运行时同版本的 CLI，可设置 `CRAWLER4J_VPK_USE_DNX=1`，脚本会改为调用 `dnx vpk --version <当前 velopack 版本>`
- 若需要显式指定 `vpk` 可执行文件路径，可设置 `CRAWLER4J_VPK_BIN=/absolute/path/to/vpk`
- 若 Windows 上的 `dnx` / `vpk` 实际是 `*.cmd` 或 `*.bat` shim，脚本会自动改用 `cmd.exe /c` 包装启动，避免在 `uv run python` 下直接 `subprocess.run(['dnx', ...])` 命中 `WinError 2`
- 若当前 Python `velopack` 包版本带 `.dev` 或 `+local` 后缀，脚本会先把它正规化成 NuGet 可接受的基础版本后再传给 `dnx --version`，避免 `invalid NuGet version`
- `uv run deploy-windows-release` 会在打包完成后继续调用系统 OpenSSH `sftp`，把 `packages/crawler4j/dist/updates/windows/` 上传到 `$CRAWLER4J_UPDATE_UPLOAD_TARGET/win/`
- `CRAWLER4J_UPDATE_UPLOAD_TARGET` 在 Windows 侧建议写成 `host:/var/www/crawler4j/` 这类 `host:path` 远端目录；若写成本地目录，脚本会改为直接复制文件
- Velopack Windows 安装目录默认位于 `%LocalAppData%\\<packId>\\current`。更新时会整体替换 `current/`，所以任何可变文件都不能写在程序目录里；`crawler4j` 当前应用数据继续落在 `%APPDATA%/Crawler4j/`，与这条约束兼容
- Windows 宿主自更新只对“通过 Velopack Setup 安装”的客户端生效；如果用户直接运行裸 `PyInstaller onedir` 目录，`检查更新` 会明确提示当前不是正式安装态
- Velopack 官方当前明确说明 Windows 不支持安装到 `C:\\Program Files` 这类特权目录；本仓当前也不提供管理员安装模式
- 若要使用 `uv run deploy-windows-release`，Windows 机器只需要启用系统自带的 OpenSSH Client，确保 `sftp` 命令在 PATH 中可用；不再要求额外安装 `rsync`

### macOS 内部 DMG + Sparkle 发布

```bash
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
```

说明：

- `uv run install-sparkle --archive ...` 用于把本地下载的 Sparkle release archive 解压到 `packages/crawler4j/vendor/macos/sparkle/`，其中至少应包含 `Sparkle.framework`、`bin/generate_keys` 与 `bin/generate_appcast`
- 发布脚本会默认读取 workspace 根的 `.env`；仓库提供 `.env.example` 作为模板，也可继续显式传 `--env-file <path>`
- 该命令会先复用现有 `PyInstaller -> Crawler4j.app` 打包链，再把 `Sparkle.framework` 复制进 bundle，并把 `SUFeedURL` / `SUPublicEDKey` / `SUEnableAutomaticChecks` / `SUEnableCodeSigningValidation=false` / `SUPackageSigningCertificate=""` 写入 `Info.plist`；随后会对改写后的 app bundle 自动执行一次 ad-hoc `codesign`
- 默认更新产物目录为 `packages/crawler4j/dist/updates/macos/`，其中至少包含 `Crawler4j-<version>.dmg`；若本机 Sparkle 分发目录内存在 `bin/generate_appcast`，还会同时生成 `appcast.xml`
- 当前 DMG 会在构建阶段挂载一次 staging 镜像，并通过 Finder 布局脚本固定窗口尺寸、图标大小与 `Crawler4j.app` / `Applications` 的摆放，用户双击后即可直接拖拽安装
- `uv run deploy-macos-internal-release` 会在完成上述构建后继续执行 `rsync -av packages/crawler4j/dist/updates/macos/ -> $CRAWLER4J_UPDATE_UPLOAD_TARGET/mac/`；目标既可以是本机静态目录，也可以是 `user@host:/var/www/crawler4j/` 这类远端 rsync 路径
- 该分发路径面向“小范围内部用户第一次手动把 app 拖到 `/Applications`、首次启动允许未知开发者、后续自动更新由 Sparkle 处理”的场景；当前会关闭宿主 app 的苹果代码签名校验，但不会关闭 Sparkle 对更新包的 EdDSA 校验
- 不要求 `Developer ID` 或 notarization，但用户不能一直直接从挂载的 DMG 中运行应用；首次安装后应从 `/Applications` 打开
- DMG 布局步骤依赖本地 Finder 图形会话；若在无桌面会话的 headless macOS 环境中执行，样式化阶段会失败并提示改为在已登录 Finder 的会话中打包
- `CRAWLER4J_SPARKLE_ROOT` 默认也可指向 `packages/crawler4j/vendor/macos/sparkle/`
- `CRAWLER4J_SPARKLE_FEED_URL` 与 `CRAWLER4J_SPARKLE_PUBLIC_ED_KEY` 为必填项
- 若要生成 `appcast.xml`，还必须提供一条私钥来源：`CRAWLER4J_SPARKLE_KEYCHAIN_ACCOUNT`、`CRAWLER4J_SPARKLE_PRIVATE_ED_KEY_FILE` 或 `CRAWLER4J_SPARKLE_PRIVATE_ED_KEY` 三选一；默认 account 仍是 `ed25519`
- `CRAWLER4J_UPDATE_UPLOAD_TARGET` 只在 `deploy-macos-internal-release` 中必填；若需要先演练命令形状，可追加 `--dry-run`

### 静态目录 / HTTPS / 二级域名建议

推荐口径：

- 建议把桌面更新站点单独放在 `updates.<主域名>`，例如 `updates.example.com`
- Sparkle feed URL 固定为 `https://updates.example.com/mac/appcast.xml`
- Windows Velopack feed URL 固定为 `https://updates.example.com/win/releases.win.json`
- 服务器静态目录固定为 `/var/www/crawler4j/`，并让 deploy 脚本把产物分别同步到 `/var/www/crawler4j/mac/` 和 `/var/www/crawler4j/win/`
- 首次部署前先创建目录：`mkdir -p /var/www/crawler4j/mac /var/www/crawler4j/win`
- Web 服务用户至少需要对这两个目录具备读权限，发布用户需要写权限；若使用 nginx + `www-data`，常见做法是把目录组设为 `www-data` 并给目录 `2755`、文件 `0644`
- 如果域名能被公网解析，优先执行 `sudo certbot --nginx -d updates.example.com` 申请 Let's Encrypt；如果是纯内网域名，则改用企业内部 CA 或已有证书体系，并把 nginx 配置里的 `ssl_certificate*` 路径替换为实际文件
- Windows 更新目录建议直接作为静态目录对外暴露，确保 `releases.win.json` 与 `.nupkg` 文件能被直接下载
- 首次上线至少确认 DNS 已解析到更新服务器，再执行 `curl -I https://updates.example.com/mac/appcast.xml`、`curl -I https://updates.example.com/mac/Crawler4j-<version>.dmg` 和 `curl -I https://updates.example.com/win/releases.win.json`；都应返回 `200`

### 测试

```bash
uv run pytest -q
```

### Root / SDK / Contracts build

```bash
uv run build
```

说明：

- 脚本会在 workspace 根目录顺序构建 `crawler4j-sdk`、`crawler4j`、`crawler4j-contracts`
- 每个包在构建前都会通过 `uv build --clear` 清空自己的 `dist/`
- 产物分别落到 `packages/crawler4j-sdk/dist/`、`packages/crawler4j/dist/`、`packages/crawler4j-contracts/dist/`
- 如果只想构建一个包，可直接写 `uv run build crawler4j`
- 长命令 `uv run python scripts/build_workspace_packages.py ...` 仍可用，但正式口径优先使用短命令

### Publish SDK / Contracts to PyPI

```bash
UV_PUBLISH_TOKEN=<your-token> uv run publish crawler4j-sdk
UV_PUBLISH_TOKEN=<your-token> uv run publish crawler4j-contracts
```

说明：

- 若使用 PyPI token，优先设置 `UV_PUBLISH_TOKEN`
- 需要预演时可先执行 `UV_PUBLISH_TOKEN=<your-token> uv run publish crawler4j-sdk --dry-run`
- 若仓库后续配置了带 `publish-url` 的 `tool.uv.index`，也可以改用 `uv publish --index <name> ...`
- 脚本会自动把 `crawler4j-sdk` / `crawler4j-contracts` 映射到各自包目录下的 `dist/*`，不需要手写文件路径

### SDK CLI

```bash
uv run python -m crawler4j_sdk.cli.commands --help
```

## 3. 当前已知运行注意事项

- `ctrip labor_workflow` 已恢复到真实执行链，但真实站点 E2E 仍需单独验证

## 4. 发布前建议最小检查

1. `uv run pytest -q`
2. Root / SDK / Contracts build
3. 根应用入口 smoke
4. 版本号与 release notes 对齐检查

## 5. docs-stratego 联动发布

- docs-stratego 源仓联动的正式口径以 `main` 为准：`.github/workflows/notify-docs-stratego.yml` 应监听 `main` 分支上的 `docs/**` 变更。
- workflow 只负责向 `uroborus2s/docs-stratego` 发送 `source-pointer-sync-requested` 事件，不在本仓直接构建或部署线上文档。
- 源仓必须在 GitHub Actions Secret 中配置 `DOCS_STRATEGO_DISPATCH_TOKEN`；该 token 只用于触发 `docs-stratego` 根仓的 `repository_dispatch`。
- workflow 会先去掉 `DOCS_STRATEGO_DISPATCH_TOKEN` 中意外带入的 `CR/LF` 再构造 `Authorization` header，避免凭据换行把 dispatch 请求拆断。
- `docs-stratego` 根仓的 source pointer 也应指向 `crawler4j` 的 `main`；如果后续切换到其他发布分支，需要同时更新源仓 workflow 分支过滤与根仓 `config/source-repos.json`。
- 根仓收到事件后会更新 `bot/sync-source-pointers` 共享 PR；线上文档仍以根仓审核合并后的 `main/master` 部署结果为准。

## 6. 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-04-22 | 新增 Windows `PyInstaller onedir + Velopack` 发布口径，说明 `package-windows-release` 的环境变量、输出目录、安装边界和与 `%APPDATA%/Crawler4j/` 的持久化兼容关系 | Codex |
| 2026-04-22 | 为 macOS Sparkle 内部分发补上“改写 bundle 后自动 ad-hoc 重签”与私钥来源配置：`generate_appcast` 现支持 keychain account、私钥文件或私钥串三种输入，不再只依赖默认 `ed25519` 账户 | Codex |
| 2026-04-22 | 补记 macOS 内部 Sparkle unsigned 分发的签名口径：`package-macos-internal-release` 现会写入 `SUEnableCodeSigningValidation=false` 与空 `SUPackageSigningCertificate`，仅关闭宿主代码签名校验，继续保留更新包 EdDSA 校验 | Codex |
| 2026-04-22 | 将 macOS 内部 DMG 构建改为固定 Finder 图标视图，打开后直接展示 `Crawler4j.app` 与 `Applications` 拖拽安装布局，并补记对 Finder 图形会话的依赖 | Codex |
| 2026-04-22 | 收口桌面更新站点目录结构为 `mac/` 与 `win/` 并列，补充 `deploy-windows-release`、静态目录创建与访问权限约定 | Codex |
| 2026-04-21 | 新增 macOS 内部 DMG + Sparkle 发布口径，说明 `package-macos-internal-release` 的环境变量、产物目录与手动拖入 `/Applications` 的使用边界 | Codex |
| 2026-04-20 | 补记桌面打包对 `sinanz` 共享 `resources/` 目录的显式收集约束，避免验证码模型资源在 PyInstaller 产物中丢失 | Codex |
| 2026-04-20 | 将 docs-stratego 联动发布说明从 `feature/task-plugin-system` 收敛到 `main` 分支口径，并补记 dispatch token 换行清理约束 | Codex |
| 2026-04-17 | 新增 `docs-stratego` 源仓通知 workflow，并补充共享 PR 联动发布说明 | Codex |
| 2026-04-02 | 下游输出补齐到运行手册和管理员指南 | Codex |
| 2026-03-28 | 同步四大模块结构下的上下游文档路径 | Codex |
| 2026-03-26 | 初始部署与运行说明 | Codex |
