# TASK-039 root wheel README 版本漂移根因

- 日期：2026-07-10（Asia/Shanghai）
- 状态：root_cause_found
- 复现：构建 `crawler4j 0.4.30` wheel 后读取 `METADATA`，包版本为 `0.4.30`，但内嵌长描述仍声明源码基线 `0.4.15`。

## 直接原因

`packages/crawler4j/README.md` 第 3 行仍硬编码 `0.4.15`，而 root `pyproject.toml` 使用该文件作为 PyPI/wheel 长描述。

## 根源原因

既有版本同步门禁覆盖根 README、应用 `pyproject.toml` 和锁文件，但没有覆盖应用包自己的 README 镜像，因此此前多个客户端版本升级都未触发失败。

## 最小修正与授权

- 只把应用包 README 的当前源码基线同步为 `0.4.30`，不新增版本 helper 或生成器。
- 以重建 wheel 并读取 `METADATA` 作为验收用例。
- 用户已明确授权升级客户端到 `0.4.30` 并提交推送，该修正属于同一版本事实同步范围。
