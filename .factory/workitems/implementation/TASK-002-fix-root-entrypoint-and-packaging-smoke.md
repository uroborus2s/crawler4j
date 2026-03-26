# TASK-002 修复根入口与打包 smoke

- 状态：DONE
- 类型：TASK
- 优先级：P0
- 估算：1.0 人/天
- 关联 ID：`TASK-002`, `BUG-001`, `REQ-001`, `REQ-004`, `NFR-002`

## 目标

- 修复根项目脚本入口
- 修复 `crawler4j.spec` 中的入口和资源路径
- 增加最小可复用 smoke 验证，证明根应用入口与打包入口一致

## 验收标准

- [x] `uv sync` 后 `.venv/bin/start` 已导入 `src.ui.app:main`
- [x] `crawler4j.spec` 不再引用不存在的 `src/main.py` 或错误资源路径
- [x] `uv run python scripts/smoke_test_ui.py` 通过
- [x] `uv run pyinstaller --noconfirm --clean --distpath /tmp/crawler4j-pyinstaller-dist --workpath /tmp/crawler4j-pyinstaller-build crawler4j.spec` 通过
