# TASK-040 实现报告

## 结果

已实现 Core `env.cookie.ensure`，公开契约保持供应商无关；模块传入的是替换后的完整 Cookie 集合，Core 删除所有未传 Cookie。

## 实现内容

- `cookie_service.py`
  - 校验并规范化公开 Cookie 字段。
  - 以完整集合比较持久化态和运行态，额外 Cookie 视为不匹配。
  - 按 `env_id` 锁住完整 read/write/stop/start/verify 链路。
  - 集合变化或运行态不一致时严格重启；成功只返回四个必需 bool。
- `provider.py`
  - BaseProvider 增加供应商无关的持久化 Cookie 可选能力。
  - VirtualBrowser Client 按实测协议读取 `data[]`、写入顶层 `cookies`。
  - `expires` 映射为 `expirationDate`，回读反向归一；Cookie 请求和响应正文不记录。
  - `stopBrowser` 严格检查响应；close 等待运行列表消失和旧 CDP TCP 端口关闭。
- `manager.py`
  - 提供 `ensure_cookies` REM 门面并复用单例 Cookie Service 锁域。
- `runtime_capabilities.py`
  - 只在 full surface 注册 `env.cookie.ensure`。
  - 限制只能操作当前 `TaskContext.env_id`。
  - 成功后从新 BrowserHandle 回绑 page/context 并重新 bind tools。
- 测试与文档
  - 新增 Service、Client、Provider 和 ATM 契约测试。
  - 更新 Core capability、API-022、memory 和 CR-020 工作项材料。

## 关键决策

- 用户明确要求全量替换：模块只传 `cticket` 时，环境最终只保留 `cticket`。
- 不采用先读完整集合再 merge 的建议。
- VirtualBrowser 当前本机接口事实优先于公开文档；兼容读取历史嵌套形态，但写请求固定采用已实测的顶层 `cookies`。

## 验证

- 初始目标集：`107 passed`；review 修复后：`118 passed`
- REM/ATM 相邻回归：`513 passed`
- 完整 unit：`1187 passed`
- Ruff format/check：通过
- `git diff --check`：通过
- 生产 Client 一次性环境探针：全量替换、空列表清空、字段映射和删除环境全部通过

详细证据见 `.factory/workitems/CR-020/evidence/TASK-040.md` 和 `.factory/workitems/CR-020/evidence/review-fix-verification.md`。
