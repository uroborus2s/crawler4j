"""SDK tools 导出与契约测试。"""

import crawler4j_sdk
from crawler4j_sdk import TaskContext, ToolSpec, ToolsCapability


class _FakeTools:
    def __init__(self):
        self.calls: list[tuple[str, dict[str, object]]] = []

    def has_tool(self, tool_name: str) -> bool:
        return tool_name in {"db.list_records", "captcha.match_slider"}

    def list_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(name="captcha.match_slider", description="识别滑块验证码缺口位置"),
            ToolSpec(name="db.list_records", description="读取模块数据集"),
        ]

    def call(self, tool_name: str, /, **kwargs):
        self.calls.append((tool_name, kwargs))
        return {"tool_name": tool_name, "kwargs": kwargs}


def test_sdk_exports_expected_stable_surface():
    fake_tools = _FakeTools()
    expected_exports = {
        "BBox",
        "ClickCaptchaDebugInfo",
        "ClickCaptchaMatchResult",
        "ClickCaptchaOrderedTarget",
        "ImageInput",
        "ModuleAssembler",
        "Point",
        "SliderCaptchaDebugInfo",
        "SliderCaptchaMatchResult",
        "TaskContext",
        "TaskFlow",
        "TaskResult",
        "TaskScript",
        "ToolSpec",
        "ToolsCapability",
    }

    assert isinstance(fake_tools, ToolsCapability)
    assert set(crawler4j_sdk.__all__) == expected_exports

    ctx = TaskContext(env_id=1, task_name="demo", tools=fake_tools)
    assert ctx.tools is fake_tools


def test_tools_capability_calls_core_extensions():
    fake_tools = _FakeTools()

    assert fake_tools.has_tool("db.list_records") is True
    assert [tool.name for tool in fake_tools.list_tools()] == [
        "captcha.match_slider",
        "db.list_records",
    ]

    ctx = TaskContext(env_id=1, task_name="demo", tools=fake_tools)
    result = ctx.tools.call("db.list_records", dataset="orders")

    assert result == {"tool_name": "db.list_records", "kwargs": {"dataset": "orders"}}
    assert fake_tools.calls == [("db.list_records", {"dataset": "orders"})]
