# CR-026 HubStudio 独立集中评审

- Reviewer：独立 Terra 子任务 `/root/cr026_independent_review`
- 独立性：未参与实现、未修改文件、未执行 Git 写操作，直接审查当前 diff、未跟踪文件、官方契约与测试。
- 最终结论：`approved`
- Findings：Critical `0`，Important `0`，Minor `1`

## 已闭环 Important

1. 浏览器状态查询改为按官方必传参数发送 `containerCodes`，并按厂商状态机仅将 `status == 0` 判断为已开启；测试覆盖 `0/1/2/3`。
2. `BrowserHandle` 的 CDP HTTP 探测客户端显式设置 `trust_env=False`，避免 loopback 请求继承系统代理。

## 复核结论

- 首轮关于缓存请求可能 no-op 的意见已撤回：官方没有只传 `browserOauths` 必然不清 Cache/Code Cache 的证据，也没有对应布尔字段；保持不删除 Cookie、LocalStorage 和 IndexedDB 的既有产品语义。
- `containerCode` 与 `browserID` 分离符合要求。
- 未修改数据库 schema、`EnvType` 或原环境列表列结构。
- Provider 注册、Cookie 转换、生命周期、厂商限制提示和旧 Provider 回归均无阻断问题。

## Minor / 残余验证限制

- HubStudio 高级指纹参数可通过 `creation_params.hubstudio` 原样传入；ATM 图形表单未提供 VirtualBrowser 的厂商专属字段级编辑，当前验收不要求该专属表单。
- 未运行真实 HubStudio E2E；待具备本地客户端、API Key 和可销毁测试环境时验证 Cache/Code Cache 实际效果与完整生命周期。
