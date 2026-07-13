# VirtualBrowser Cookie API 实机探针证据

- 时间：2026-07-13
- 范围：本机已配置 VirtualBrowser Management API
- 安全边界：只创建并删除一次性环境；只使用 `example.com/.org/.net` 和固定探针 Cookie；未读取、修改或启动现有环境；输出不含 API Key 和 Cookie value。

## 探针设计

1. 创建带一个 bootstrap Cookie 的一次性环境，使 Cookie 文件存在。
2. 调用 `POST /api/updateCookie` 写入探针 Cookie A、B。
3. 调用 `GET /api/getCookie?id=<id>` 回读并检查字段。
4. 再次只传入 A 的新值。
5. 回读确认 A 是否更新、未传入的 B 是否保留。
6. 在 `finally` 中删除一次性环境。

## 实测事实

| 检查项 | 实测结果 |
|---|---|
| `updateCookie` 官方文档形态 `id + cookie.mode/jsonStr` | HTTP 400，服务端提示缺少 `cookies` |
| `updateCookie` 本机实际请求形态 | `{"id": <id>, "cookies": [...]}` |
| `getCookie` 官方文档形态 `data.cookie.jsonStr` | 与本机不符 |
| `getCookie` 本机实际响应形态 | `{"success": true, "data": [cookie, ...]}` |
| 新环境无 Cookie 文件直接更新 | HTTP 500，`COOKIE_FILE_NOT_EXIST` |
| 第一次传 A、B | 回读 2 个，均持久化 |
| 第二次只传更新后的 A | 回读仅 1 个，B 被删除 |
| 更新语义 | **全量替换**，不是 merge/patch |
| 直接传公开字段 `expires` | 未按指定有效期持久化 |
| 传线字段 `expirationDate` | float Unix seconds 原值持久化 |
| `sameSite="Lax"` | 回读归一为 `"lax"` |
| domain/path/secure/httpOnly | 按传入值持久化 |
| 一次性环境清理 | 每次探针均删除成功 |
| 生产 `VirtualBrowserClient.get_cookies/replace_cookies` 复测 | 通过；不是临时 HTTP helper 自证 |
| 空列表全量替换 | 回读 0 个 Cookie，确认清空全部 Cookie |

## 最终一次探针摘要

```json
{
  "created_disposable_env": true,
  "create_initialized_cookie_file": true,
  "first_update_persisted_both": true,
  "first_update_attributes": {
    "domain": true,
    "path": true,
    "expires": true,
    "secure": true,
    "httpOnly": true,
    "sameSite": true
  },
  "second_update_updated_target": true,
  "second_update_retained_omitted_cookie": false,
  "observed_update_semantics": "full_replace",
  "after_first_cookie_count": 2,
  "after_second_cookie_count": 1,
  "empty_list_cleared_all": true,
  "used_production_client_methods": true,
  "deleted_disposable_env": true
}
```

说明：最终一次探针在 Core 契约字段和 Provider 字段之间显式执行 `expires → expirationDate`，证明该适配可保持带小数的 Unix seconds。
