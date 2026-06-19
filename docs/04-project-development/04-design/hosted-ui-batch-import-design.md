# Hosted UI 批量导入方案

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 方案待实现  
**负责人：** 当前仓库维护者  
**主要读者：** 架构 | Core 开发 | SDK 开发 | QA | 模块开发者  
**上游输入：** `REQ-010` | `API-008` | `module-hosted-ui-framework.md` | `module-config-runtime-data-contract.md`  
**下游输出：** `implementation-plan.md` | `test-plan.md` | Hosted UI / Contracts / SDK / Core 实现任务  
**关联 ID：** `REQ-010`, `NFR-010`, `API-019`, `CR-016`, `TASK-030`, `TASK-031`, `TASK-032`, `TASK-033`, `TASK-034`  
**最后更新：** 2026-06-19

## 1. 结论

Hosted UI 批量导入能力应由宿主负责文件和剪贴板读取、解析、限制和脱敏，模块只接收结构化行数据并负责业务校验、暂存、去重和落库。

V1 范围固定为：

- 页面级和 `DataTable` 工具栏支持自定义按钮
- 按钮可调用 `@ui_action`、调度 workflow，或打开宿主导入弹窗
- 导入弹窗支持 `xlsx/csv` 文件上传和剪贴板粘贴
- 手工 JSON / 表格行录入作为可选增强，不能阻塞文件和剪贴板主链路
- 宿主把数据统一转换成 import payload 后交给模块
- 模块返回批次结果，宿主展示汇总并可跳转到 `import_data_records` 页面查看批次明细
- 安全限制由宿主统一执行：文件类型、文件大小、最大行数、敏感字段日志脱敏

## 2. 背景

当前 Hosted UI 已收口为 `@page(...)` + `@ui_action(...)` 注解模式，`DataTable` 是页面组件，宿主负责通用渲染和交互，模块负责业务数据语义。账号、Cookie、劳保账号、携游账号等业务对象都需要批量导入，但模块运行时代码不能直接读取本地文件，也不应自行处理桌面文件选择、剪贴板和 Excel 解析。

因此批量导入应作为 Hosted UI 的宿主能力：宿主提供统一入口和解析链路，模块只处理已经结构化的业务 payload。

## 3. 设计目标

- 为页面和表格提供一致的 toolbar 自定义按钮能力。
- 让模块可以通过 schema 声明“导入”按钮，而不是硬编码宿主 UI。
- 让宿主统一读取 Excel/CSV/剪贴板内容，避免模块触碰本地文件系统。
- 让导入 payload 可被 `@ui_action` 或 workflow 消费。
- 让用户在宿主侧看到批次导入结果、失败行数和后续处理入口。
- 为从暂存表导入业务表的逐条状态展示预留正式页面约定。

## 4. 非目标

- 不在 V1 实现任意文件格式导入；只支持 `xlsx/csv`。
- 不让模块代码接收本地文件路径、文件句柄或原始二进制内容。
- 不把导入逻辑塞进 `@page_action`；浏览器页面操作仍只由 workflow/component 调用。
- 不由宿主理解业务字段含义、去重规则或业务落库规则。
- 不在 V1 强制提供通用导入暂存物理表；暂存表和业务落库仍由模块用 `@data_table` / `ctx.db` 声明和实现。

## 5. 页面与工具栏 schema

### 5.1 页面级工具栏

页面 schema 可声明页面级工具栏：

```json
{
  "type": "Page",
  "title": "账号管理",
  "toolbar": {
    "actions": [
      {
        "id": "import_accounts",
        "label": "导入",
        "icon": "upload",
        "action": {
          "type": "open_import_dialog",
          "target_type": "ctrip_account",
          "submit": {
            "type": "ui_action",
            "name": "import_accounts"
          }
        }
      }
    ]
  },
  "children": []
}
```

### 5.2 表格工具栏

`DataTable` 可声明表格级工具栏动作，宿主把动作渲染在表格工具栏中：

```json
{
  "type": "DataTable",
  "table_id": "accounts",
  "toolbar": {
    "actions": [
      {
        "id": "import_accounts",
        "label": "导入账号",
        "icon": "upload",
        "action": {
          "type": "open_import_dialog",
          "target_type": "ctrip_account",
          "submit": {
            "type": "ui_action",
            "name": "import_accounts"
          }
        }
      }
    ]
  },
  "data_source": {
    "type": "query_handler",
    "name": "query_accounts"
  }
}
```

### 5.3 支持的动作类型

| 动作类型 | 语义 | 宿主行为 |
|---|---|---|
| `ui_action` | 调用模块 `@ui_action` | 维持当前 Hosted UI 同步动作模型，按 action params 绑定参数 |
| `workflow` | 调度模块 workflow | 通过 ATM 创建受控运行实例，把 payload 写入 workflow 运行态元数据，不直接在 UI 线程执行 |
| `open_import_dialog` | 打开宿主导入弹窗 | 宿主读取文件/剪贴板/手工输入，组装 payload 后再按 `submit` 分发 |

workflow 动作必须走宿主调度和进度展示，不能被实现成在 renderer 内直接调用 workflow 函数。

## 6. 导入弹窗

### 6.1 数据来源

| 来源 | V1 状态 | 宿主职责 |
|---|---|---|
| Excel 文件 | 必须支持 | 仅允许 `.xlsx`，读取第一个 sheet 或用户选择的 sheet，按表头解析行 |
| CSV 文件 | 必须支持 | 仅允许 `.csv`，识别 UTF-8 / UTF-8 BOM，必要时提供编码错误提示 |
| 剪贴板粘贴 | 必须支持 | 支持从表格软件复制的 TSV/CSV 文本，按首行表头或用户选择列映射解析 |
| 手工 JSON / 表格行 | 可选支持 | 作为高级入口，不影响文件和剪贴板主流程 |
| API 来源 | 预留 | 使用同一 payload 中的 `source_type="api"`，V1 不做宿主 API 拉取 |

### 6.2 限制策略

默认限制建议：

- 文件类型：`.xlsx`、`.csv`
- 单文件大小：默认 10 MB，宿主可配置，但不得超过全局安全上限
- 单次最大行数：默认 5000 行，宿主可配置，但不得超过全局安全上限
- 空行跳过，表头重复或缺失时在预览阶段阻断提交
- 解析失败必须显示可定位原因，例如文件类型、编码、sheet、行号、列名

### 6.3 预览与列映射

宿主导入弹窗至少展示：

- 来源名称、来源类型、解析行数
- 前若干行预览
- 原始列名
- 可选的业务字段映射
- 最大行数和文件大小限制提示
- 提交前的目标类型 `target_type`

业务字段标准化可以由模块在 `@ui_action` / workflow 内执行；宿主只负责把原始行解析成结构化对象，并保留可选字段映射结果。

## 7. Import Payload

宿主传给模块的 payload 固定为 JSON-compatible dict：

```json
{
  "source_type": "file",
  "source_name": "accounts.xlsx",
  "target_type": "ctrip_account",
  "rows": [
    {
      "source_row_no": 2,
      "business_key": "13800000000",
      "payload": {
        "phone": "13800000000",
        "remark": "A组"
      },
      "raw_payload": {
        "手机号": "13800000000",
        "备注": "A组"
      }
    }
  ]
}
```

字段规则：

| 字段 | 责任方 | 说明 |
|---|---|---|
| `source_type` | 宿主 | `file`、`clipboard`、`manual`、`api` |
| `source_name` | 宿主 | 文件名、剪贴板、手工录入或 API 名称；不得包含本地绝对路径 |
| `target_type` | schema 声明 | 业务目标类型，例如 `ctrip_account`、`labor_account`、`xc_account`、`web_account`、`cookie` |
| `rows[].source_row_no` | 宿主 | 原始来源行号，Excel/CSV 表头后第一条通常为 2 |
| `rows[].business_key` | 宿主或模块 | 若 schema 提供 key 映射则宿主填充，否则模块可在处理时补齐 |
| `rows[].payload` | 宿主 + 模块约定 | 标准化业务字段；宿主可按列映射生成，模块仍需校验 |
| `rows[].raw_payload` | 宿主 | 原始列名和值，用于错误定位和模块自定义映射 |

## 8. 模块调用模型

### 8.1 `@ui_action` 提交

适合快速校验、写入导入暂存表并返回批次汇总：

```python
@ui_action(name="import_accounts", label="导入账号")
async def import_accounts(context: TaskContext, import_payload: dict) -> dict:
    ...
```

宿主传参名默认为 `import_payload`，也允许 schema 通过 `submit.payload_param` 指定。

### 8.2 workflow 提交

适合长耗时导入、需要复用对象图或需要后续自动处理的场景。宿主通过 ATM 调度 workflow，并把 payload 写入：

```python
ctx.runtime["import_payload"]
```

workflow 调度必须使用宿主任务进度和日志链路展示状态。workflow 不声明 parameters，仍遵守 0.4.0 对象装配契约。

## 9. 结果展示

模块处理完成后返回标准结果：

```json
{
  "batch_id": "imp-20260619-001",
  "total_rows": 100,
  "staged_rows": 92,
  "failed_rows": 8,
  "target_type": "ctrip_account",
  "records_page_id": "import_data_records"
}
```

宿主负责：

- 展示批次 ID、总行数、成功写入暂存表行数、失败行数
- 如果模块声明或返回 `records_page_id="import_data_records"`，提供跳转按钮
- 跳转时带上 `batch_id`、`target_type` 页面参数
- 支持刷新当前表格或当前页面

模块负责：

- 创建或更新导入批次记录
- 将每行暂存为可查询明细
- 标记每行解析、校验、暂存、导入业务表的状态
- 在 `import_data_records` 页面中展示批次明细和后续“从暂存表导入业务表”的逐条结果

逐条状态建议至少包含：

- `pending`
- `staged`
- `validation_failed`
- `imported`
- `import_failed`
- `skipped_duplicate`

## 10. 安全与日志

宿主必须执行：

- 不把本地文件路径传给模块，只传 `source_name`
- 不在日志中输出完整 `rows`、`raw_payload` 或文件内容
- 对字段名或目标类型命中 `token`、`cookie`、`password`、`secret`、`authorization`、`credential`、`passwd` 的值做脱敏
- 弹窗预览中允许用户看到自己导入的数据，但系统日志、任务日志和错误摘要必须脱敏
- 上传文件解析只在本机内存或安全临时对象中完成；除非用户明确保存导入批次，宿主不落地原始文件
- 超过文件大小、行数或列数限制时，提交前阻断

## 11. 实施拆分

| 任务 | 范围 | 产物 |
|---|---|---|
| `TASK-030` | Contracts / SDK schema 契约 | `toolbar.actions`、`open_import_dialog`、payload/result helper、扫描校验 |
| `TASK-031` | 宿主导入弹窗与解析 | Excel/CSV/剪贴板解析、预览、限制、脱敏 |
| `TASK-032` | Hosted UI 分发与结果展示 | renderer 分发 `ui_action` / workflow、结果弹窗、页面跳转 |
| `TASK-033` | 暂存明细页面约定 | `import_data_records` 页面参数、逐条状态展示、从暂存导入业务表的结果口径 |
| `TASK-034` | 测试与文档收口 | 单测、集成/验收、开发者指南、测试计划、memory |

## 12. 待实现验证

- toolbar 自定义按钮 schema 规范化和非法动作拒绝
- 文件类型、文件大小、最大行数限制
- Excel / CSV / 剪贴板解析
- 敏感字段日志脱敏
- `@ui_action` 收到标准 import payload
- workflow 收到 `ctx.runtime["import_payload"]`
- 模块返回结果后，宿主展示汇总并跳转 `import_data_records`
- 从暂存表导入业务表后，逐条成功 / 失败状态可见

## 13. 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-06-19 | 新增 Hosted UI 批量导入方案，登记 toolbar 自定义按钮、宿主导入弹窗、标准 payload、结果展示、安全限制和任务拆分 | Codex |
