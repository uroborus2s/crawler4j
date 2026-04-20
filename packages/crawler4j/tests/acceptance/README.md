# Acceptance Fixtures

这组 pytest 只负责“正式验收夹具”和“非真实站点证据”。

当前覆盖：

- `test_sdk_cli_scaffold_package_acceptance.py`
  从 `crawler4j module init` 到 `crawler4j package verify`
- `test_host_devlink_acceptance.py`
  宿主 `host devlink add/list/remove`
- `test_host_install_local_zip_acceptance.py`
  宿主本地 ZIP `host install preview/apply --skip-remote-check`
- `test_host_install_boundaries_acceptance.py`
  锁定“目录源码只能走 DevLink，不能走 install”的边界
- `test_acceptance_gate_matrix.py`
  表达正式验收 gate 的命令矩阵：`check structure -> check release -> check full -> package verify`

这组夹具故意不做的事：

- 不访问真实站点
- 不依赖真实 `ctrip` 账号
- 不替代 `ctrip` 真实站点 E2E 放行

结论边界：

- 这些测试只证明 SDK CLI、宿主 DevLink、本地 ZIP 安装和验收 gate 编排在隔离临时目录里可复用
- 发布是否真正放行，仍要补 `docs/04-project-development/06-testing-verification/ctrip-real-site-e2e-closeout.md` 里的 live E2E 证据
