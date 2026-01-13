# 5.10 系统基础能力（System Capabilities）

本章定义 Framework Core 必须提供的基础系统能力，包括版本管理、应用升级（OTA）与基础偏好设置。

## 5.10.1 版本管理 (Version Management)

系统必须具备清晰的版本定义与兼容性检查机制，以确保 Core、SDK 与 Modules 之间的协同工作。

### 1. 语义化版本 (Semantic Versioning)
Core、SDK 与 Modules 均遵循 `Major.Minor.Patch` 语义化版本规范：
- **Major**: 不兼容的 API 修改或架构变更。
- **Minor**: 向下兼容的功能性新增。
- **Patch**: 向下兼容的问题修正。

### 2. 依赖兼容性矩阵
Core 在加载模块时，MUST 校验模块声明的依赖版本：
- **SDK Compatibility**: 模块依赖的 `crawler4j_sdk` 版本必须与当前环境兼容。
- **Core Compatibility**: 模块可声明 `min_core_version`，Core 低于此版本时拒绝加载。

### 3. VersionService 职责
- 提供 `get_current_version()` 获取当前 Core 版本。
- 提供 `check_compatibility(requirement)` 校验版本约束。

### 4. UI 交互设计 (UI Design)
- **全局显示 (Global Display)**:
  - **状态栏 (Status Bar)**: 主窗口底部右侧常驻显示当前版本号 `vX.Y.Z`。鼠标悬停提示 "Click to check for updates"。
  - **标题栏 (Title Bar)**: (可选) 应用名称后跟随版本号，如 `Crawler4j v1.0.0`。

- **关于弹窗 (About Dialog)**:
  - **布局**: 居中模态对话框（Modal）。
    - 顶部: 应用图标 (Logo)。
    - 中部: 应用名称、当前版本号 `vX.Y.Z (Build <CommitHash>)`。
    - 底部: 版权信息 (Copyright)、官网链接。
  - **交互**: 提供 [Check for Updates] 按钮。点击触发 `VersionService` 检查。
  - **状态反馈**:
    - Check 中: 显示 Spinner 动画。
    - 已经是最新: 显示 "Your software is up to date" 绿字提示。
    - 有更新: 变为连接样式的 "Update Available"，点击跳转 OTA 流程。

## 5.10.2 应用升级 (OTA Updates)

Framework Core 内置 OTA (Over-The-Air) 升级能力，确保用户能及时获取功能更新与安全修复。

### 1. 升级流程 (Update Flow)
1.  **Check (检查)**: 定时或手动向升级服务器请求 `update_manifest.json`。
2.  **Notification (通知)**: 发现新版本时，通过 UI Host 弹出通知或在设置页提示。
3.  **Download (下载)**: 用户确认后，后台下载升级包（支持断点续传），UI 展示进度条。
4.  **Verification (校验)**: 下载完成后，MUST 校验文件哈希（SHA256）与数字签名（GPG/RSA），确保包未被篡改。
5.  **Installation (安装)**:
    - 既然是 Python 桌面应用，通常采用“重启替换”策略。
    - 释放新文件到临时区 -> 重启应用 -> Bootloader 将新文件覆盖至安装目录 -> 启动新版。

### 2. 职责分离
- **UpdateService (Logic)**: 执行 HTTP 请求、文件 I/O、哈希计算、签名校验。不依赖任何 UI 控件。
- **UpdateDialog (UI)**: 订阅 UpdateService 的 `progress` 事件更新进度条；发送 `start_download` / `cancel` 命令。

### 3. 异常处理
- **网络错误**: 自动重试 3 次，失败后通知用户。
- **校验失败**: 立即删除下载的临时文件，并报警提示“文件可能损坏或被篡改”。
- **回滚机制**: 安装过程若失败，Bootloader 应能恢复旧版本（如通过保留备份）。

### 4. UI 交互设计 (UI Design)
- **更新提示弹窗 (Update Available Prompt)**:
  - **触发**: 自动检查或手动检查发现新版本时。
  - **内容**:
    - 标题: "New Version Available: vX.Y.Z"
    - 摘要: 展示 Release Notes（如果过长则显示可滚动区域），重点高亮 Breaking Changes。
  - **操作**:
    - [Update Now]: 推荐操作，高亮，立即触发下载。
    - [Remind Me Later]: 关闭弹窗，下次启动再提醒。
    - [Skip This Version]: 写入 Ignore List，该版本不再提示。

- **下载进度 (Download Progress)**:
  - **形式**: 推荐作为**任务**显示在 Dashboard 状态栏，或非模态的 Toast，通过点击可展开详情。也可使用模态窗避免用户在更新时操作。
  - **展示**: 进度条 (0-100%)、下载速度、剩余时间预估。
  - **控制**: 提供 [Pause] / [Resume] / [Cancel] 按钮。

- **重启确认 (Restart Confirmation)**:
  - **触发**: 下载完成且校验成功 (Verified) 后。
  - **提示**: "Update is ready to install. Crawler4j helps to restart to apply changes."
  - **操作**: [Restart & Install] (默认焦点)。

## 5.10.3 基础偏好设置 (Basic Preferences)

Settings 模块提供全局配置界面，配置数据由 ConfigSystem 持久化。

### 1. 核心设置项
| 分类 | 设置项 | 说明 | 默认值 |
| :--- | :--- | :--- | :--- |
| **General** | **Locale** | 界面语言 (zh_CN / en_US) | System Default |
| | **Theme** | 界面主题 (Light / Dark / System) | System |
| | **Updates** | 自动检查更新 (On / Off) | On |
| **Network** | **Proxy Mode** | 代理模式 (No Proxy / System / Manual) | System |
| | **HTTP Proxy** | HTTP 代理地址 (Manual 模式有效) | Empty |
| **Resources** | **Workspace** | 数据存储与日志目录路径 | `~/.crawler4j` |
| | **Max Concurrency** | 全局最大并发任务数 | 4 |

### 2. 配置生效
- **即时生效**: 多数 UI 相关设置（如 Theme）应即时应用。
- **重启生效**: 这里的设置（如 Locale、Proxy 核心变动）若需重启，UI 必须明确提示。

### 3. UI 交互设计 (UI Design)
- **设置中心 (Settings Center)**:
  - **布局**: 标准的两栏式设计。
    - **左侧导航**: 垂直列表，展示分类图标+名称 (General, Network, Resources, Extensions, About)。选中的分类有高亮背景。
    - **右侧内容**: 对应分类的表单区域，支持滚动。
  - **控件交互**:
    - **Switch/Toggle**: 用于布尔值 (比如 "Run on Startup")，点击通过动画切换。
    - **Combo Box**: 用于枚举选择 (Theme: Dark/Light)。
    - **Directory Picker**: 路径输入框右侧附带 [Browse...] 按钮，调用系统原生文件选择器。
  - **保存策略**:
    - **Auto-Save (推荐)**: 控件值改变即触发 `ConfigSystem.update(key, value)`，无需显式“保存”按钮。
    - **Dirty State**: 若有需重启生效的变更，底部弹出 Snackbar "Settings changed. Restart required to apply all changes." 并在该条目旁显示黄色小点。
