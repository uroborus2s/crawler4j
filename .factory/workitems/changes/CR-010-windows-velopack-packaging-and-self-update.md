# CR-010 Windows 桌面发布改为 PyInstaller onedir + Velopack

- 状态：DONE
- 类型：CR
- 优先级：P0
- 估算：2.0 人/天
- 关联 ID：`CR-010`, `TASK-024`, `REQ-001`, `REQ-004`
- 提出日期：2026-04-22

## 变更动机

- 当前仓库已经具备 `PyInstaller` 固定目录打包能力，但 Windows 仍缺正式安装器、自更新闭环和发布口径。
- 现有发布风险已明确登记为“Windows desktop delivery artifacts are still missing”，继续维持“只会出裸目录”的状态会阻塞正式交付。
- 现有宿主应用数据已经稳定落在 `%APPDATA%/Crawler4j/`，与 Velopack Windows 路径“替换 `current/` 目录、不保留应用内可变文件”的约束天然兼容，适合直接作为主方案落地。

## 变更范围

- 保留 `PyInstaller onedir` 作为 Windows 宿主编译基线。
- 新增 Windows Velopack 发布脚本，负责把 onedir 产物打成 Velopack installer / package feed。
- 为宿主应用新增 Windows Velopack 运行时桥接与 `UpdateService` 后端分派。
- 同步更新实施计划、架构/接口设计、测试计划、运维说明、用户设置口径与 `.factory/memory/`。

## 非目标

- 本轮不实现 `Program Files` / 需要管理员权限的安装目录方案。
- 本轮不补 Windows 代码签名与 CI 发布自动上传。
- 本轮不重写现有 macOS Sparkle 分发路线。
- 本轮不引入“静默后台自动下载后再提示安装”的复杂 UI 流程，Windows 先收口为宿主侧手动检查并触发升级。

## 当前进展

- 已完成：正式 CR/TASK 登记、实施方案与运维文档同步。
- 已完成：Windows Velopack 发布脚本、宿主启动早期钩子、更新服务后端分派与最小回归测试。
- 待完成：Windows 真机打包、签名与正式发布主机接入。

## 完成判定

- Windows 正式发布命令可以从 `PyInstaller onedir` 产物继续打出 Velopack 安装器与更新目录。
- 宿主应用在 Windows 打包态会尽早运行 Velopack 启动钩子，并能通过统一 `UpdateService` 触发检查更新。
- 正式文档、测试计划、README 与 `.factory/memory/` 已同步，不再声明“Windows 还没有正式发布链”。
