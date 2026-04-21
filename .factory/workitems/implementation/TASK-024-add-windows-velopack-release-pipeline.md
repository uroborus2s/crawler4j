# TASK-024 为 Windows 建立 PyInstaller onedir + Velopack 发布与宿主自更新闭环

- 状态：DONE
- 负责人：Codex
- 优先级：P0
- 估算：2.0 人/天
- 关联 ID：`TASK-024`, `CR-010`, `REQ-001`, `REQ-004`, `NFR-003`

## 目标

- 把 Windows 宿主交付从“只有 PyInstaller onedir 裸目录”推进到“有安装器、有更新源、有宿主自更新入口”的正式形态。
- 维持现有 `PyInstaller onedir` 作为基线，不为 Windows 单独引入第二套应用编译产物。
- 让宿主更新能力在 UI 侧继续复用统一 `UpdateService`，而不是让 Windows 分叉出独立入口。

## 范围

- 新增 Windows Velopack 发布脚本与更新配置落盘逻辑。
- 在宿主系统层新增 Velopack 运行时桥接，并把 `UpdateService` 改为按平台分派 Sparkle / Velopack。
- 更新 `README`、部署文档、测试计划、实施方案、工厂记忆与相关用户说明。

## 非目标

- 不实现 Windows 发布上传器、GitHub Release 推送或对象存储同步脚本。
- 不实现 Windows 端复杂更新弹窗与分步下载 UI。
- 不改变当前应用数据目录、模块安装目录与日志目录布局。

## 验收标准

- `uv run package-windows-release` 可以在已完成的 Windows `package-desktop` 产物基础上继续生成 Velopack 发布目录。
- 宿主应用在 Windows 打包态启动时会先执行 Velopack 启动钩子，且不影响内嵌 debug worker / debugpy adapter 子进程分流。
- `系统设置 -> 关于 -> 检查更新` 在 Windows Velopack 安装态不再只返回“当前无法检查更新”。
- 相关回归测试已补齐，覆盖脚本命令形状、更新配置读取、平台后端分派和入口集成。

## 完成说明

- 已新增 `scripts/package_windows_release.py`，负责读取 Velopack 发布配置、写入 Windows 宿主更新配置文件，并调用 `vpk`/`dnx vpk` 生成安装器与更新目录。
- 已新增 `src.core.system.velopack`，隔离 Velopack 启动钩子、Windows 更新配置读取和运行时更新调用。
- `UpdateService` 已从“只包装 Sparkle”收口到“统一 UI 门面 + Sparkle / Velopack 后端分派”，`src.ui.app:main` 也已在 GUI 初始化前接入 Windows Velopack bootstrap。
- 正式文档、README、测试计划和 `.factory/memory/` 已同步到新的 Windows 发布口径。
