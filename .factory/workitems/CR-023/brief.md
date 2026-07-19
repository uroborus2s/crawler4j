# 宿主 HTTP/2 与 Brotli 运行时依赖修复需求简报

- 项目：crawler4j
- Work item：`CR-023`
- 任务：`TASK-043`
- 状态：`requirements_ready`
- 场景：`fix_bug`
- 来源：用户提供的已确认根因、修复目标与验收口径
- 文档版本：`0.2.0`
- 日期：2026-07-19
- 目标协议：Core `0.4.0` / `core-native-v2`

## 版本历史

| 版本 | 修改内容 | 日期 | 修改人 | 审核 | 批准 |
|---|---|---|---|---|---|
| `0.1.0` | 初版：补齐宿主 HTTP/2/Brotli 能力、发布物收集、运行时自检与模块依赖边界说明 | 2026-07-19 | Codex | 用户已给出精确验收口径 | 用户已明确要求修复并提交 |
| `0.2.0` | 按用户架构裁决改为 Core 统一 `http.request`；模块不得直接 import 或安装第三方网络库 | 2026-07-19 | Codex | 用户明确否决模块直连宿主第三方包 | 用户明确要求宿主统一提供方法 |

## 目标

作为在 crawler4j 宿主进程内运行的模块，我希望通过 Core 的统一 `ctx.tools.call("http.request")` 方法提交 HTTP/2 请求，并由宿主源码安装与桌面发布物统一提供 `httpx`、HTTP/2 和 Brotli 实现，以便模块 ZIP 不安装、也不直接调用第三方网络库。

## 非目标

- 不把 `ctrip_crawler` 降级到 HTTP/1.1。
- 不吞掉 `ImportError`，不自动回退协议。
- 不让 ZIP 安装器执行任意模块 `pyproject.toml` 依赖安装。
- 不在本轮设计通用模块依赖解析、隔离环境或任意第三方依赖安装系统。
- 不在 crawler4j 宿主工作项内越界修改 `ctrip_crawler` 外部仓库；该模块改接宿主方法是完成端到端验收的显式后续步骤。

## 根因输入

- 复现与边界证据：`.factory/workitems/CR-023/evidence/root-cause-reproduction.md`
- 根因报告：`.factory/workitems/CR-023/reports/http2-runtime-dependency-root-cause.md`
- 直接原因：宿主只声明 `httpx>=0.28.1`，宿主锁文件和 `.venv` 没有 `h2/hpack/hyperframe/brotli`。
- 根源原因：模块 ZIP 安装器只解压、校验并导入模块，不安装 ZIP 内 `pyproject.toml`；导入预检也不会执行延迟到请求路径的 `httpx.Client(http2=True)`。

## 需求

### `REQ-014`：宿主提供共享 HTTP/2/Brotli 运行时能力

- 优先级：P0
- 宿主 `crawler4j` 包必须声明 `httpx[http2,brotli]>=0.28.1`。
- `uv.lock` 必须解析并锁定 `h2`、`hpack`、`hyperframe` 与 CPython 的 `brotli`。
- PyInstaller 发布配置必须显式收集上述动态/可选导入，不能依赖碰巧被静态分析发现。
- full runtime surface 必须注册异步 `http.request`，模块只传标准 Python 类型，宿主内部构造和发送请求。
- 方法必须支持有序/重复请求头、原始 body、HTTP/HTTPS 代理、禁用环境代理、HTTP/2 强制检查和 Brotli 解码。
- 模块不得直接 import `httpx/h2/brotli`，也不得在 ZIP 中携带或安装它们。

### `REQ-015`：宿主能力必须可执行验证

- 优先级：P0
- 源码宿主解释器、从新 wheel 隔离安装的解释器和桌面发布物都必须能导入 `h2`、`brotli`，并成功构造及关闭 `httpx.Client(http2=True)`。
- 桌面入口必须提供不启动 GUI、不初始化数据库的宿主 HTTP 能力检查模式，以便直接验证冻结发布物。
- 验证失败必须返回非零状态，不得回退到 HTTP/1.1。

### `REQ-016`：模块安装边界与预检限制必须明确

- 优先级：P1
- 模块 ZIP 安装仍只负责安全解压、manifest/lock 校验、导入预检和激活，不执行模块依赖安装。
- 模块导入预检不能证明所有延迟运行时路径的可选依赖均可用；文档必须明确这一限制。
- 本轮为宿主统一 HTTP 工具增加显式 surface、运行时检查与测试；通用 manifest 能力声明/版本协商登记为后续架构项。

## 验收标准

- `AC-023-001`：给定 full runtime `TaskContext`，模块可 await `http.request`，且有序请求头、原始 body、代理和 HTTP/2 要求由宿主准确执行；非 HTTP/2 响应明确失败。
- `AC-023-002`：给定构建出的 crawler4j wheel 在全新虚拟环境安装，则无需安装模块 ZIP 内依赖即可通过同一 HTTP 能力检查。
- `AC-023-003`：给定 PyInstaller 桌面发布物，以 HTTP 能力检查参数启动时返回 0，并证明 `h2`、`brotli` 导入和 HTTP/2 client 构造成功。
- `AC-023-004`：包元数据与 PyInstaller 配置测试锁定 `httpx[http2,brotli]` 和四个可选运行包，防止后续依赖或打包回退。
- `AC-023-005`：模块 ZIP 仍不安装自身依赖；用户升级到新宿主后，无需在模块 ZIP 中单独安装 `h2`。
- `AC-023-006`：文档分别列明开发环境、源码安装、wheel/发布物和桌面发布的更新/验证步骤。
- `AC-023-007`：现有模块导入预检行为保持兼容，并记录“通用模块能力声明/依赖协商”后续项，不扩大为任意依赖安装器。
- `AC-023-008`：`ctrip_crawler` 外部仓库移除生产运行路径的 `httpx` 直接调用，改为宿主 `http.request` 后，才可声明房型请求端到端修复；宿主提交不得伪造该外部证据。

## 非功能需求

### `NFR-014`：发布一致性

- 类型：兼容性 / 可维护性
- 指标：依赖声明、lock、wheel METADATA、PyInstaller 收集配置和三类运行环境自检结果一致；任一缺失即验收失败。
- 验证：`TC-071` 聚焦测试、wheel 隔离安装 smoke、桌面冻结运行时 smoke。

## 领域模块映射与 baseline 影响

- 领域模块：`MOD-001` 根应用/Core、`MOD-003` 模块运行边界、`MOD-005` Docs/Release Surface。
- owner：`API-024` 与内部依赖/冻结发布物由 crawler4j Core/Release owner 负责；业务模块只消费宿主方法并处理业务响应。
- 接口边界：新增 full runtime `http.request` 公共工具与内部诊断入口；不新增数据库或 UI 契约。
- baseline 影响：更新模块工具 API、模块边界与发布 baseline；无数据库或 UI baseline 变化。

## 风险与回滚

- 风险：Brotli 是平台 wheel/扩展模块，必须在目标平台本机构建并执行冻结运行时 smoke。
- 风险：PyInstaller 对动态导入的自动发现可能变化，因此显式收集并以发布物执行结果为准。
- 回滚：撤回宿主 extras、lock、冻结收集和诊断入口；但会重新暴露已确认缺陷，因此不能作为协议降级方案。
- 后续项：为模块声明机器可读的宿主能力需求，并在 DevLink/ZIP 安装、升级和激活时统一协商；不得通过直接执行模块依赖安装实现。
