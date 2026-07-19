# 宿主 HTTP/2 与 Brotli 运行时能力实施计划

> **给执行者：** 计划评审通过后，把状态交还 `using-shanforge` 流程总控判断执行。

**目标：** 让模块通过 crawler4j 统一 `http.request` 方法使用 HTTP/2/Brotli，第三方网络栈只由源码环境、wheel 和 PyInstaller 宿主提供，并为模块安装边界留下可执行诊断和明确文档。

**架构：** full runtime surface 通过 `ctx.tools.call("http.request")` 提供标准类型 HTTP 契约，Core ATM 内部以 `httpx.AsyncClient` 实现；宿主包元数据是内部依赖事实源，uv lock 固化解析结果，PyInstaller spec 显式收集动态依赖；Core system 提供纯诊断函数，UI 入口以专用参数在 GUI/数据库初始化前执行它。模块 ZIP 不执行第三方依赖安装，也不直接 import 宿主实现包。

**技术栈：** Python 3.12、uv、httpx 0.28.x、h2/hpack/hyperframe、brotli、PyInstaller、pytest、ruff。

**工作项：** `CR-023`

**任务：** `TASK-043`

**状态：** `approved`

## 输入

- 已批准需求：`.factory/workitems/CR-023/brief.md`
- 根因报告：`.factory/workitems/CR-023/reports/http2-runtime-dependency-root-cause.md`
- 相关摘要：`.factory/memory/runtime-brief.md`、`.factory/memory/architecture.summary.md`、`.factory/memory/tech-stack.summary.md`
- 已读取正式文档：模块边界、v0.4.0 shipping/troubleshooting、PRD、测试计划和追踪矩阵。

## 范围

### 目标

- 宿主依赖与 lock 纳入 HTTP/2/Brotli extras。
- full runtime surface 增加异步 `http.request`，保持请求头/body 并拒绝 HTTP/2 降级。
- 源码、wheel 和冻结发布物执行同一能力检查。
- PyInstaller 显式收集四个可选运行包。
- 提升根应用补丁版本并同步正式发布事实。
- 记录模块 ZIP 依赖边界与通用能力协商后续项。

### 非目标

- 不安装模块 `pyproject.toml`。
- 不越过当前 workspace 修改 `ctrip_crawler`；其迁移到宿主方法作为外部仓库交付步骤记录，端到端结论以该步骤完成为前提。
- 不新增任意第三方依赖解析器、模块私有 venv 或 HTTP/1.1 回退。

## 文件

| 类型 | 路径 | 职责 |
|---|---|---|
| 修改 | `packages/crawler4j/pyproject.toml`, `uv.lock` | 声明并锁定宿主 extras，提升根应用版本 |
| 新建/修改 | `packages/crawler4j/src/core/atm/http_tools.py`, `runtime_capabilities.py` | 实现并仅在 full surface 注册宿主 HTTP 方法 |
| 新建 | `packages/crawler4j/src/core/system/http_runtime.py` | 导入关键包并构造 HTTP/2 client 的唯一能力检查 |
| 修改 | `packages/crawler4j/src/ui/app.py` | 在 GUI/数据库初始化前提供能力检查入口 |
| 修改 | `packages/crawler4j/crawler4j.spec` | 显式收集 h2/hpack/hyperframe/brotli |
| 测试 | `packages/crawler4j/tests/unit/test_core/test_system/test_http_runtime.py` | 真实宿主解释器能力检查与失败语义 |
| 测试 | `packages/crawler4j/tests/unit/test_core/test_atm/test_http_tools.py` | 工具 surface、请求保真、HTTP/2 和输入边界 |
| 测试 | `packages/crawler4j/tests/unit/test_ui/test_app.py` | 诊断入口分派顺序与退出码 |
| 测试 | `packages/crawler4j/tests/unit/test_sdk/test_packaging_config.py` | 包 extras 与冻结收集配置回归 |
| 文档 | `docs/03-developer-guide/v0.4.0/{shipping,troubleshooting}.md` | 模块/宿主依赖边界和升级步骤 |
| 文档 | `docs/04-project-development/{03-requirements/prd.md,04-design/{api-design,module-boundaries}.md,06-testing-verification/test-plan.md,10-traceability/{requirements-matrix,interface-matrix}.md}` | 正式需求、API-024、架构、TC-071 与追踪 |
| 发布 | `README.md`, `packages/crawler4j/README.md`, `docs/04-project-development/07-release-delivery/{version-governance,release-notes}.md` | 根应用新补丁版本和发布说明 |
| 记忆 | `.factory/memory/{runtime-brief,current-state,requirements.summary,architecture.summary,tech-stack.summary,traceability.summary,tasks.summary,tests.summary,change-summary,release.summary}.md`、`.factory/project.json` | 当前状态和证据索引 |

## 边界

- 层级：Module → `ctx.tools/http.request` → Core HTTP implementation → httpx optional transports/decoders。
- 领域：Core/Release owner 提供统一能力；模块 owner 只负责标准类型输入和业务响应。
- 接口归属方：`http.request` 是 `API-024` 模块公开工具；`verify_host_http_runtime()` 仅为宿主内部发布诊断。
- 下游依赖：uv resolver、wheel METADATA、PyInstaller Analysis 和目标平台扩展 wheel。
- 禁止耦合：不解析/执行模块项目依赖，不把 HTTP/2 失败转换成正常 HTTP/1.1 请求。

## 任务 1：TASK-043 宿主 HTTP 运行时纵向切片

**任务切片：**

- 设计方案：以统一工具、包元数据、lock、运行时检查和冻结入口形成五层一致性门禁。
- 接口设计：`http.request` 接收标准类型并返回结构化 response mapping；`verify_host_http_runtime()` 返回 `httpx/h2/brotli/http2_client` 结果，失败保留依赖异常；入口参数成功返回 0。
- UI：`N/A`，诊断参数在 GUI 创建前完成，不新增可见界面。
- 测试设计：两轮 RED 锁定依赖/诊断与架构修订后的 `http.request` 缺失；GREEN 覆盖 surface、请求保真、拒绝降级、extras、真实解释器、入口、PyInstaller、wheel 和桌面冻结 smoke。
- 开发：先依赖和纯诊断，再入口与 spec，最后版本/文档/memory。
- 单测：真实导入与 client 构造不发网络请求；mock 仅用于入口分派失败路径。
- review：实现者只进入 `ready_for_review`，独立 reviewer 检查依赖/打包/诊断/文档一致性。
- 集成测试：新 wheel 隔离安装；macOS 本机 PyInstaller app 执行诊断参数；Windows 标记目标平台后续复验。
- 失败断言：缺测试设计则失败；UI 写 `N/A` 但无原因则失败；发现占位语则失败。

- [x] **步骤 1：RED——增加依赖、运行时与打包失败测试**

  - 断言宿主依赖精确包含 `httpx[http2,brotli]>=0.28.1`。
  - 断言真实宿主解释器可导入 h2/brotli 并构造 client。
  - 断言 UI 诊断入口先于 updater、数据库和 QApplication。
  - 断言 spec 显式收集 h2/hpack/hyperframe/brotli。

- [x] **步骤 2：运行 RED**

```bash
.venv/bin/pytest packages/crawler4j/tests/unit/test_core/test_system/test_http_runtime.py packages/crawler4j/tests/unit/test_ui/test_app.py packages/crawler4j/tests/unit/test_sdk/test_packaging_config.py -q -p no:cacheprovider
```

期望：新增断言因 extras、诊断实现或 hidden imports 缺失失败；既有测试无新增无关故障。

- [x] **步骤 3：GREEN——依赖、诊断入口与冻结收集**

  - 修改宿主 pyproject 后运行 `uv lock` 与 `uv sync --all-packages`。
  - 新增纯能力检查并在专用 argv 分支调用。
  - spec 对四个包执行 `collect_submodules`，保留平台扩展自动收集。
  - 不捕获并降级 HTTP/2 初始化错误。

- [x] **步骤 3A：架构修订 RED/GREEN——统一宿主 HTTP 方法**

  - 用户明确要求模块不得直接调用宿主第三方包后，增加 `http.request` 缺失 RED（3 failed）。
  - 新增 Core HTTP 工具并只注册到 full surface；以宿主 `httpx.Request + AsyncClient.send` 保持请求输入。
  - 结构化返回不泄漏第三方对象，`require_http2` 拒绝协议降级。

- [x] **步骤 4：GREEN 与邻近回归**

```bash
uv run pytest packages/crawler4j/tests/unit/test_core/test_atm/test_http_tools.py packages/crawler4j/tests/unit/test_core/test_system/test_http_runtime.py packages/crawler4j/tests/unit/test_ui/test_app.py packages/crawler4j/tests/unit/test_sdk/test_packaging_config.py packages/crawler4j/tests/unit/test_core/test_mms/test_external_module_install.py -q -p no:cacheprovider
uv run ruff check packages/crawler4j/src/core/atm/http_tools.py packages/crawler4j/src/core/atm/runtime_capabilities.py packages/crawler4j/src/core/system/http_runtime.py packages/crawler4j/src/ui/app.py packages/crawler4j/tests/unit/test_core/test_atm/test_http_tools.py packages/crawler4j/tests/unit/test_core/test_system/test_http_runtime.py packages/crawler4j/tests/unit/test_ui/test_app.py packages/crawler4j/tests/unit/test_sdk/test_packaging_config.py
```

期望：全部 exit code 0。

- [x] **步骤 5：构建与三类运行环境验证**

```bash
uv lock --check
uv run build crawler4j
uv run package-desktop
```

  - 检查 wheel METADATA 含 httpx extras。
  - 在全新临时 venv 安装 wheel并执行 `verify_http_runtime()`。
  - 执行 macOS `Crawler4j.app/Contents/MacOS/Crawler4j --crawler4j-verify-http-runtime`。
  - Windows 必须在 Windows 构建机重建并执行同一参数；本轮不伪造跨平台通过。

  当前结果：源码、隔离 wheel 与 macOS arm64 PyInstaller app 通过；Windows 明确保留为目标平台后续 gate。

- [x] **步骤 6：正式文档、证据和记忆同步**

  - 更新需求、模块边界、shipping、troubleshooting、测试计划、追踪矩阵和新版本发布事实。
  - 写 TASK-043 evidence/report/review input 与 ledger。
  - memory 只记录状态、约束和产物路径。

- [x] **步骤 7：全量质量门**

```bash
uv run pytest packages/crawler4j/tests/unit -q -p no:cacheprovider
uv run ruff check .
uvx --from docs-stratego docs-stratego source validate --repo-path .
python -m json.tool .factory/project.json >/dev/null
git diff --check
```

期望：可重复门禁 exit code 0；已知环境基线若复现须单独记录，不能写成目标失败。

实际：定向/邻近 `152 passed`、全量 unit `1265 passed`；Ruff、lock、docs-stratego、JSON、diff gate 通过。独立评审已批准，Minor 已按 TDD 修复。

## 测试策略

- 红灯：依赖声明、真实运行时、入口分派/spec 收集，以及架构修订后的统一 HTTP 工具断言。
- 绿灯：同一聚焦集合。
- 定向回归：Core system、UI app、packaging config、模块外部安装。
- 邻近回归：版本服务与桌面打包脚本测试。
- 全量回归：crawler4j unit、Ruff、lock、docs、JSON 和 diff。
- 发布验证：wheel 隔离安装 + 本机 PyInstaller app 执行诊断参数。
- 未运行项：Windows 冻结发布物执行。
- 未运行原因：PyInstaller 产物平台绑定，必须在 Windows 构建机生成，macOS 不能替代。

## 文档同步

- 正式文档：`REQ-014`~`REQ-016`、`NFR-014`、`API-024`、`TC-071`、模块边界与 v0.4.0 交付说明。
- `.factory/memory/`：当前版本、状态、风险、验证和路径索引。
- 工作项流水账：根因、需求、计划、RED/GREEN、验证、review、人工确认和提交分事件记录。

## 评审门

- 计划评审：`passed`
- 任务评审：`approved`
- 验证：`passed`
- 人工确认：`approved`（用户本轮明确要求按项目规则测试、提交）
- 提交：`passed`
- 记忆同步：`passed`

## 计划自审

- 规格覆盖：AC-023-001 至 AC-023-008 全部映射；AC-023-008 明确由外部模块仓库完成，不在宿主证据中伪造。
- 占位符扫描：无占位交付。
- 发现占位语则失败：通过。
- 缺测试设计则失败：通过，覆盖 RED/GREEN、源码、wheel、冻结物和平台限制。
- UI 写 `N/A` 但无原因则失败：通过，诊断在 GUI 初始化前返回。
- 类型一致性：同一 `verify_http_runtime()` 被源安装、wheel 和冻结入口复用。
- 可构建性：文件、命令、结果和平台边界明确。
- Shanforge 门禁：包含 evidence、独立 review、verification、memory、ledger 和提交。
