# 版本治理规则

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** 发布负责人 | Tech Lead | Dev | QA  
**上游输入：** `pyproject.toml` | `src/__version__.py` | Git tag | 子包 `pyproject.toml`  
**下游输出：** `release-notes.md` | `deployment-guide.md` | `.factory/project.json`  
**关联 ID：** `CR-001`, `TASK-004`, `REQ-004`, `NFR-002`  
**最后更新：** 2026-03-26  

## 1. 规则

1. 根应用当前工作区版本以根 `pyproject.toml` 的 `[project].version` 为唯一事实源。
2. `src/__version__.py` 必须与根 `pyproject.toml` 完全一致，只作为运行时显示镜像。
3. Git tag 只表示最近一次正式发布，可以落后于当前工作区版本。
4. `crawler4j-sdk` 与 `crawler4j-contracts` 是独立版本线，不要求与根应用版本号相同。
5. 发布说明必须同时区分：
   - 当前工作区版本
   - 最近一次正式发布 tag
   - SDK / Contracts 当前发布版本

## 2. 当前版本事实

| 对象 | 当前值 | 说明 |
|---|---|---|
| 根应用工作区版本 | `0.1.2.dev20260326` | 当前仓库 HEAD 的未发布开发版 |
| 根应用运行时版本 | `0.1.2.dev20260326` | 与根 `pyproject.toml` 镜像一致 |
| 最近正式发布 tag | `v0.1.1` | 最新已知正式发布 |
| SDK | `1.0.3` | 当前已发布版本 |
| Contracts | `1.0.1` | 当前已发布版本 |

## 3. 为什么这样定义

- 过去的问题不是“版本号多少”，而是同一份仓库里同时存在根包版本、运行时版本和 tag 口径漂移。
- 当前工作区已经明显领先于 `v0.1.1`，如果继续把根应用显示成 `0.1.1`，会让维护者误以为当前源码仍等同于最新正式发布。
- 采用开发版号后，维护者可以明确区分“当前工作区”和“最近正式发布”。

## 4. 发布前动作

在下一次正式发布根应用前，至少完成：

1. 将根 `pyproject.toml` 与 `src/__version__.py` 从开发版切到目标正式版本
2. 更新 `docs/04-project-development/07-release-delivery/release-notes.md`
3. 复验 `uv run pytest -q`
4. 复验 `uv run python scripts/smoke_test_ui.py`
5. 复验 Root / SDK / Contracts build
6. 为根应用打对应 Git tag

## 5. 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-03-26 | 建立根应用 / 运行时 / tag / SDK / Contracts 的统一版本治理规则 | Codex |
