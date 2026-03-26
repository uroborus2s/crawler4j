# TASK-009 统一 `docs/` 文档体系并移除 MkDocs 静态站职责

- 状态：DONE
- 类型：TASK
- 优先级：P1
- 估算：1.0 人/天
- 关联 ID：`TASK-009`, `REQ-005`, `DOC-002`

## 目标

- 将根 `docs/` 收敛为单一 Markdown 文档树
- 停用本仓 MkDocs 静态站能力，但保留 `docs/` 作为事实源

## 验收标准

- 根 `docs/` 不再保留平行的 legacy 专题根目录
- 仓库不再包含 `mkdocs.yml`
- `pyproject.toml` 不再声明 MkDocs 相关开发依赖
