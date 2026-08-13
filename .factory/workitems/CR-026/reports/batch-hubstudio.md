# CR-026 HubStudio 批次实现摘要

## 实现

- 新增独立 `HubStudioClient` / `HubStudioProvider`，复用现有 `BaseProvider`、`Environment` 和 `BrowserHandle`。
- 实现创建、导入、存在/状态查询、打开/CDP 连接、关闭、销毁、名称/代理更新、指纹刷新、Cookie 读写和单环境缓存清理。
- `containerCode` 保存在原 `external_id/browser_id`，`browserID` 只在 Provider 内存映射中管理。
- 在 Provider registry、ConfigCenter、ExternalApp、REM、ATM 和 REM UI 中做加法映射。
- 保留数据库、公共环境契约、`EnvType` 和环境列表列结构不变。

## 开发期整改

- 修复官方 `data.containers` 响应读取。
- 修复缓存清理的 start/stop/clear 顺序及 cached `browserID` 路径。
- 修复运行中环境销毁的 stop/delete 顺序。
- 分离创建 `proxyServer` 与更新 `proxyHost` 契约。
- 增加 HTTP/业务状态和 cache 部分失败检测。
- 修复浏览器状态接口必传参数和 `0/1/2/3` 状态判断。
- 禁用 CDP loopback 探测的环境代理继承。

## 关注项

- HubStudio 不提供完整指纹回读和 location 原地修复，本实现不伪造这两项能力。
- 真实客户端 E2E 留待有可销毁 HubStudio 环境时执行。
- 高级指纹可通过 `creation_params.hubstudio` 透传；本轮不新增 HubStudio 专属 ATM 指纹表单。
