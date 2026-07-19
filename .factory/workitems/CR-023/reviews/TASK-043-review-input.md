# TASK-043 独立评审输入

## 评审目标

确认 CR-023 是否按用户裁决实现“第三方 HTTP 栈由宿主统一提供方法”，且没有把模块 ZIP 依赖安装、HTTP/1.1 回退或外部业务模块未完成事项伪装成已完成。

## 重点检查

1. `src/core/atm/http_tools.py` 的输入输出是否保持第三方类型隔离、请求保真和 HTTP/2 拒绝降级。
2. `runtime_capabilities.py` 是否仅在 full surface 暴露 `http.request`，ToolSpec 是否标记 async。
3. pyproject/lock/wheel METADATA/PyInstaller hidden imports + distribution metadata 是否一致。
4. runtime diagnostic 是否真实构造 HTTP/2 client，冻结入口是否在 GUI/数据库前短路。
5. tests 是否覆盖 surface、ordered/duplicate headers、raw body、proxy、协议降级、无效输入、依赖与冻结配置。
6. 正式 docs/factory/memory 是否明确模块不得直接 import/install、外部 ctrip 接线和 Windows 验证未完成。

## 验证证据

- `.factory/workitems/CR-023/evidence/TASK-043.md`
- `.factory/workitems/CR-023/reports/TASK-043.md`
- 首轮评审输入：定向 `145 passed`；全量 unit `1258 passed`；Ruff/lock/docs/JSON/diff 通过。
- 评审修复后：定向 `152 passed`；全量 unit `1265 passed`；重复请求头、Brotli 解码和严格布尔校验已回归，文档/记忆事实已同步，wheel 隔离安装与 macOS 冻结物均按最终代码重建并复验。
- wheel 隔离与 macOS frozen runtime 均输出 `http2_client=ok`。

## 已知非目标

- 不修改 `/Users/uroborus/PythonProject/ctrip_crawler` 外部仓库。
- 不增加 manifest capability schema 或模块依赖安装器。
- 不声称 Windows 发布物或真实携程房型请求 E2E 已通过。
