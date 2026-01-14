# Crawler4j Agent Skills Definition

## 1. 调试与运行技能 (Runtime Skills)

### @run-plugin-debug (单插件调试)
- **描述**: 在不启动完整 GUI 的情况下，独立运行和调试特定的 Module 任务。这是验证插件逻辑的首选方式。
- **命令模式**: 
  ```bash
  uv run python scripts/debug_runner.py --module <module_id> --task <task_name> [--headless]