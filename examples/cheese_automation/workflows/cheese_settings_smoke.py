"""定位模块内的 Cheese Android 设置页冒烟脚本。"""

from pathlib import Path

from crawler4j_contracts import TaskContext, TaskResult, workflow


@workflow(
    name="cheese_settings_smoke",
    label="Cheese 设置页冒烟测试",
    description="返回随模块安装的 Cheese 测试脚本路径和运行方式",
)
class CheeseSettingsSmokeWorkflow:
    """向用户暴露设备侧 Cheese 脚本。"""

    async def run(self, ctx: TaskContext) -> TaskResult:
        script_path = Path(__file__).resolve().parents[1] / "cheese" / "settings_smoke.js"
        if not script_path.is_file():
            return TaskResult.fail("Cheese 测试脚本不存在", error="cheese_script_missing")

        ctx.logger.info(f"Cheese 测试脚本: {script_path}")
        return TaskResult.ok(
            message="请使用 Cheese 官方 VSCode/IDEA 插件在已授权 Android 设备上运行脚本",
            data={
                "script_path": str(script_path),
                "runner": "Cheese VSCode/IDEA plugin",
            },
        )
