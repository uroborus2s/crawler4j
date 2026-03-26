# BUG-001 根入口与 PyInstaller 规格漂移

- 状态：DONE
- 类型：BUG
- 优先级：P0
- 估算：1.0 人/天
- 关联 ID：`BUG-001`, `REQ-001`, `REQ-004`, `NFR-002`, `TASK-002`
- 发现日期：2026-03-26

## 问题

根项目的声明入口和实际入口曾经漂移：

- `pyproject.toml` 的 `start` 曾指向 `src.main:main`
- 当前仓库并不存在 `src/main.py`
- `crawler4j.spec` 曾指向 `src/main.py` 和 `src/assets/icon.png`
- 实际可导入入口位于 `src/ui/app.py`

## 证据

- 初始发现时 `uv run start` 失败：`ModuleNotFoundError: No module named 'src.main'`
- 修复后 `.venv/bin/start` 已导入 `src.ui.app:main`
- 修复后 `uv run python scripts/smoke_test_ui.py` 与 PyInstaller build 均通过

## 影响

- 根项目 release wiring 不可信
- 构建成功不能证明最终桌面应用可运行
- README 与打包说明容易误导维护者

## 验收标准

- [x] 根脚本入口与真实入口一致
- [x] PyInstaller 入口与资源路径一致
- [x] smoke 验证覆盖根入口
