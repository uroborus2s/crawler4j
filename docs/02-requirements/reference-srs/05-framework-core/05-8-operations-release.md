# 5.8 部署发布与运维 (Operations & Release)

## 5.8.1 发布形态

- **桌面应用**: 提供 DMG (macOS) / MSI (Windows) 安装包。
- **依赖打包**: 必须内置 Python 运行时 (PyInstaller/Nuitka) 或自动检测 uv 环境。
- **浏览器管理**: 不内置浏览器二进制，通过 Playwright 首次启动下载或配置本地 Path。

## 5.8.2 运维流程

### 迁移 (Migrations)
- **数据库**: 使用 Alembic 或手写 SQL 脚本管理 SQLite schema 变更。
- **兼容性**: 新版 Core 必须兼容旧版 TaskData，或者提供自动迁移工具。

### 故障排查 (Diagnostics)
- **一键诊断包**:
    - `crawler.log` (最近 10MB)
    - `app_config.yaml` (脱敏)
    - `env_status.json` (当前环境池快照)
    - `system_info` (OS, Ram, CPU)

## 5.8.3 版本策略

遵循 SemVer 2.0.0：
- **SDK 版本**: 严格兼容性控制。SDK 升级不应强制模块升级 (除非大版本)。
- **Core 版本**: Core 升级需向下兼容 SDK。
