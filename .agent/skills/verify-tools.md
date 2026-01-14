# Skills: Verification Tools

## Skill: Debug Plugin (@run-plugin-debug)
- **Description**: 在不启动完整 UI 的情况下调试单个插件。
- **Command**: `uv run python scripts/debug_runner.py --module {module_name} --task {task_name}`
- **Usage**: 当用户要求“测试一下这个插件”时调用。

## Skill: Verify Browser Environment (@verify-browser)
- **Description**: 检查 Playwright 环境和异步浏览器驱动。
- **Command**: `uv run python tests/verify_async_browser.py`

## Skill: Database CLI (@db-cli)
- **Description**: 直接检查数据库状态。
- **Command**: `uv run python scripts/db_cli.py {args}`