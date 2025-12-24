# 研究报告：自动化爬虫 GUI

## 决策

### 浏览器控制策略

**决策**: 使用 BitBrowser/VirtualBrowser 本地 API 启动配置，然后通过 **Playwright** 连接到返回的 CDP (Chrome DevTools Protocol) 端点。
**理由**:
- BitBrowser/VirtualBrowser 提供通用的 HTTP API (通常是 localhost:54345 或类似端口) 来启动配置。
- API 响应包含 WebSocket URL (CDP 端点)。
- Playwright 的 `browser.connect_over_cdp()` 方法可以直接附加到现有 Chrome 实例。
- Playwright 是异步原生的，与 Python `asyncio` 集成更自然。
**替代方案**:
- *Selenium*: API 较旧，异步支持差，反检测能力弱。
- *RPA 工具*: 对于跨多个站点的复杂"搜索 -> 提交"逻辑，灵活性较差。

### 浏览器选择与安装检测

**决策**: 在设置界面提供 BitBrowser / VirtualBrowser 选择，并在选择后自动检测是否安装。
**检测方法**:
- **Windows**: 检查注册表 (`HKEY_LOCAL_MACHINE\SOFTWARE\...`) 或常见安装路径 (`C:\Program Files\BitBrowser\`)。
- **macOS**: 检查 `/Applications/BitBrowser.app` 或使用 `mdfind` 命令。
- **API 探测**: 尝试连接到默认 API 端口 (如 54345)，若连接成功则说明已启动。
**理由**:
- 避免用户选择未安装的浏览器导致运行时错误。
- 提供即时反馈，改善用户体验。

### 并发模型

**决策**: 使用 `qasync` 将 `asyncio` 事件循环与 PyQt6 集成，配合 Playwright 异步 API。
**理由**:
- **响应性**: Playwright 原生异步，无需额外线程。
- **简化**: 避免 `QThread` 与 `asyncio` 混用的复杂性。
- **通信**: 使用 Qt 信号/槽机制更新 UI。
**替代方案**:
- *QThreadPool*: 可行但增加同步复杂度；Playwright 的异步接口更适合 `asyncio`。

### 双账号池设计

**决策**: 分离携程账号池和劳保账号池为两个独立表。
**理由**:
- 携程和劳保是两个独立系统，用户名/密码格式可能不同。
- 独立管理便于统计和状态跟踪。
- 未来可能需要不同的调度策略 (如携程账号轮换频率高于劳保)。

### 数据存储

**决策**: SQLite (`sqlite3` 标准库)。
**理由**:
- **并发性**: WAL 模式支持多读单写。
- **查询**: 易于计算统计数据。
- **便携性**: 单个文件，无需服务器。

## 已解决的遗留问题

- **BitBrowser API**: 确认存在用于打开/关闭和获取 CDP 端点的本地 API。
- **VirtualBrowser API**: 类似架构，端口和 API 路径略有不同，需抽象为统一接口。
- **并发**: `qasync` + Playwright 异步 API 足以处理 10+ 并发浏览器。
