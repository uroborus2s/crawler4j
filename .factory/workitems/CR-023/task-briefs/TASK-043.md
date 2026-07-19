# TASK-043 任务简报

## 工作项

- 工作项：`CR-023`
- 任务：`TASK-043`
- 状态：`ready_for_review`
- 上游计划：`.factory/workitems/CR-023/plan.md`
- 流水账：`.factory/workitems/CR-023/ledger.jsonl`

## 目标

交付可发布的 crawler4j 宿主统一 HTTP/2/Brotli 方法：`API-024`、内部依赖、lock、PyInstaller、诊断入口和三类环境验证一致，模块 ZIP 无需也不得自行安装或直接调用 `h2/httpx`。

## 输入

- 需求：`.factory/workitems/CR-023/brief.md`
- 根因：`.factory/workitems/CR-023/reports/http2-runtime-dependency-root-cause.md`
- 计划：`.factory/workitems/CR-023/plan.md`
- 必读文件：宿主 pyproject/lock、`crawler4j.spec`、`src/ui/app.py`、packaging/UI/system 测试。

## 允许修改

- `.factory/workitems/CR-023/**`
- 计划文件表中列出的依赖、Core ATM/system、UI 入口、spec、测试、正式文档、发布事实与 memory 文件。

## 禁止修改

- `/Users/uroborus/PythonProject/ctrip_crawler/**`
- 任意模块依赖安装器、HTTP/1.1 降级或异常吞噬逻辑。
- 与本任务无关的代码和用户改动。

## 实施与验证

1. 增加 RED 测试并确认目标失败。
2. 实现 full surface `http.request`，修改宿主 extras 并更新 lock/环境。
3. 实现纯诊断与桌面入口参数，显式收集冻结依赖。
4. 跑定向、邻近与全量回归。
5. 构建 wheel 和桌面包，分别执行隔离/冻结运行时 smoke。
6. 同步正式 docs、factory evidence、memory 与 ledger。
7. 生成独立评审输入；实现者状态只到 `ready_for_review`。
8. 明确外部 `ctrip_crawler` 必须改接 `ctx.tools` 后才能完成业务端到端验收。

## 输出

- 验证证据：`.factory/workitems/CR-023/evidence/TASK-043.md`
- 实现报告：`.factory/workitems/CR-023/reports/TASK-043.md`
- 评审输入：`.factory/workitems/CR-023/reviews/TASK-043-review-input.md`
- 流水账：`.factory/workitems/CR-023/ledger.jsonl`
