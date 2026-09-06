# CR-026 HubStudio 跟随 IP 指纹补充评审

- Reviewer：独立 Terra 子任务 `/root/cr026_independent_review`
- 独立性：未参与实现，仅只读检查 `73cc1906` 后的 diff、官方 `advancedBo` 契约和定向测试；未修改文件或 Git 状态。
- 结论：`approved`
- Findings：Critical `0`、Important `0`、Minor `0`

## 结论

- 仅解析出有效 `proxyServer` 时注入跟随 IP 策略；手动代理和 IP 池解析后的代理共用该路径。
- none、system、无效代理和无代理不会注入 `advancedBo`。
- 保留原高级指纹字段，并强制 `languageType=0`、`geoRule=0`。
- 未虚构 HubStudio 未公开的时区跟随字段。
- 测试覆盖有代理覆盖冲突值、保留其他字段，以及无代理不注入。
