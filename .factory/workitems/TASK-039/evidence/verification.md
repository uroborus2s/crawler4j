# TASK-039 客户端 0.4.30 验证证据

- 日期：2026-07-10（Asia/Shanghai）
- 状态：VERIFICATION_PASSED / READY_TO_PUSH
- 范围：源码版本、锁文件、版本文档、本地提交和 `origin/0.4.0` 推送
- 非范围：桌面安装包、tag、GitHub release、PR

## 远端预检

- `git fetch origin 0.4.0` 首次因临时 TLS 错误失败，重试成功。
- 本地 HEAD 与 `origin/0.4.0` 均为 `a0f96cc81d5347b2b9a466f52b12d572d55e6700`，无领先或落后提交。

## 验证结果

- `uv lock`：成功更新 `crawler4j 0.4.29 -> 0.4.30`；`uv lock --check` exit code `0`。
- 版本服务 + 打包配置：`65 passed in 0.10s`，exit code `0`。
- 完整 unit：`1135 passed in 28.01s`，failures/errors/skipped 为 `0/0/0`。
- 全仓 Ruff：exit code `0`，`All checks passed!`。
- `.factory/project.json`：`python -m json.tool` exit code `0`。
- docs-stratego：exit code `0`，`pages=86 contracts=0`。
- UI smoke：exit code `0`，Shell structure 与 Dashboard async refresh 通过。
- `git diff --check`：exit code `0`。

## 构建与元数据

- `crawler4j-0.4.30-py3-none-any.whl`：SHA256 `5a8c5b5b766e3375b9f84ae4ce8649deb232b4be235c0488a0ab29b7b7611e3c`。
- `crawler4j-0.4.30.tar.gz`：SHA256 `4110cee95b73294e2fb14fe228a886509c20b6f1d6c94e1401599fdf9f10e538`。
- wheel `METADATA`：`Name: crawler4j`、`Version: 0.4.30`、`crawler4j-contracts<0.5.0,>=0.4.3`。
- 首次构建发现内嵌包 README 仍写 `0.4.15`；根因记录于 `../reports/root-cause.md`。最小同步后重建，内嵌 README 已为 `0.4.30`。

## 未运行项

- 未构建或上传 macOS / Windows 桌面安装包。
- 未创建 tag、GitHub release 或 PR。
- 本地提交与远端 push 尚待执行。
