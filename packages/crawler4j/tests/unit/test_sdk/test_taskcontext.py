"""TaskContext 单元测试。

测试用例覆盖:
    - TC_SDK_001: 能力注入测试
    - TC_SDK_012: Mock Context 创建测试
    - 工具方法测试
    - 子任务调用测试
"""

import asyncio
import time
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from unittest.mock import AsyncMock, MagicMock

import pytest

from crawler4j_contracts import EnvAction, TaskContext, TaskResult, TaskSignal, ToolSpec, ToolsCapability
import crawler4j_contracts.context as contracts_context
from crawler4j_sdk.context import DefaultHttpClient, HttpClient

# === 测试夹具 ===

@pytest.fixture
def basic_context() -> TaskContext:
    """创建基础 TaskContext。"""
    return TaskContext(
        env_id=1,
        task_name="test_task",
        config={"timeout": 30, "retry": 3},
    )


@pytest.fixture
def mock_context_with_page() -> TaskContext:
    """创建带 Mock Page 的 TaskContext。"""
    ctx = TaskContext(
        env_id=1,
        task_name="test_task",
        config={},
    )
    ctx.page = MagicMock()
    ctx.page.screenshot = AsyncMock()
    ctx.page.goto = AsyncMock()
    ctx.logger = MagicMock()
    return ctx


# === 能力注入测试 ===

class TestTaskContextInjection:
    """测试 TaskContext 能力注入。"""
    
    def test_basic_fields_exist(self, basic_context: TaskContext):
        """TC_SDK_001: 验证基础字段存在。"""
        assert basic_context.env_id == 1
        assert basic_context.task_name == "test_task"
        assert isinstance(basic_context.config, dict)
        assert isinstance(basic_context.state, dict)
        assert isinstance(basic_context.runtime, dict)
    
    def test_logger_injection(self, basic_context: TaskContext):
        """验证 logger 注入。"""
        assert basic_context.logger is not None
        # 应该可以调用日志方法
        basic_context.logger.info("测试日志")
        assert hasattr(basic_context.logger, "json")
    
    def test_http_client_defaults_to_none(self, basic_context: TaskContext):
        """验证 contracts 层默认不再提供运行时 HTTP 实现。"""
        assert basic_context.http is None

    def test_http_client_can_be_injected(self, basic_context: TaskContext):
        """验证 HTTP 客户端可按协议显式注入。"""

        class _FakeHttpClient:
            async def get(self, url: str, **kwargs):
                return {"method": "get", "url": url, "kwargs": kwargs}

            async def post(self, url: str, data=None, **kwargs):
                return {"method": "post", "url": url, "data": data, "kwargs": kwargs}

        fake_http = _FakeHttpClient()

        assert isinstance(fake_http, HttpClient)

        basic_context.http = fake_http
        assert basic_context.http is fake_http

    @pytest.mark.asyncio
    async def test_sdk_default_http_client_forwards_requests_to_aiohttp_session(self, monkeypatch):
        """验证 README 建议的默认 HTTP 客户端只做最小请求转发。"""
        calls: list[tuple[str, str, dict[str, object]]] = []

        class _FakeResponse:
            def __init__(self, payload: dict[str, object]):
                self._payload = payload

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return None

            async def json(self):
                return self._payload

        class _FakeSession:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return None

            def get(self, url: str, **kwargs):
                calls.append(("get", url, kwargs))
                return _FakeResponse({"method": "get", "url": url, "kwargs": kwargs})

            def post(self, url: str, **kwargs):
                calls.append(("post", url, kwargs))
                return _FakeResponse({"method": "post", "url": url, "kwargs": kwargs})

        monkeypatch.setitem(sys.modules, "aiohttp", SimpleNamespace(ClientSession=lambda: _FakeSession()))

        client = DefaultHttpClient()
        get_result = await client.get("https://example.com/api", timeout=3)
        post_result = await client.post("https://example.com/api", data={"key": "value"}, headers={"x-id": "1"})

        assert get_result == {"method": "get", "url": "https://example.com/api", "kwargs": {"timeout": 3}}
        assert post_result == {
            "method": "post",
            "url": "https://example.com/api",
            "kwargs": {"json": {"key": "value"}, "headers": {"x-id": "1"}},
        }
        assert calls == [
            ("get", "https://example.com/api", {"timeout": 3}),
            ("post", "https://example.com/api", {"json": {"key": "value"}, "headers": {"x-id": "1"}}),
        ]
    
    def test_page_can_be_none(self, basic_context: TaskContext):
        """验证 page 可以为 None。"""
        assert basic_context.page is None
        assert basic_context.context is None
    
    def test_tools_can_be_none(self, basic_context: TaskContext):
        """验证 tools 可以为 None。"""
        assert basic_context.tools is None

    def test_tools_capability_can_be_injected(self, basic_context: TaskContext):
        """验证 tools 能力可以注入。"""

        class _FakeTools:
            def has_tool(self, tool_name: str) -> bool:
                return tool_name == "captcha.match_slider"

            def list_tools(self) -> list[ToolSpec]:
                return [ToolSpec(name="captcha.match_slider", description="识别滑块验证码缺口位置")]

            def call(self, tool_name: str, /, **kwargs):
                return {"tool_name": tool_name, "kwargs": kwargs}

        fake_tools = _FakeTools()

        assert isinstance(fake_tools, ToolsCapability)

        basic_context.tools = fake_tools
        assert basic_context.tools is fake_tools


class TestMockContext:
    """测试 Mock Context 创建。"""
    
    def test_create_mock_context(self):
        """TC_SDK_012: 验证可以创建 Mock Context。"""
        # 创建最小 Mock Context
        ctx = TaskContext(
            env_id=999,
            task_name="mock_task",
            config={"test": True},
        )
        
        assert ctx.env_id == 999
        assert ctx.task_name == "mock_task"
        assert ctx.config["test"] is True
    
    def test_mock_context_with_mock_page(self):
        """验证可以注入 Mock Page。"""
        mock_page = MagicMock()
        mock_page.goto = AsyncMock()
        
        ctx = TaskContext(
            env_id=1,
            task_name="test",
            page=mock_page,
        )
        
        assert ctx.page is mock_page


# === 工具方法测试 ===

class TestTaskContextUtilities:
    """测试 TaskContext 工具方法。"""
    
    def test_get_config(self, basic_context: TaskContext):
        """验证 get_config 方法。"""
        assert basic_context.get_config("timeout") == 30
        assert basic_context.get_config("retry") == 3
        assert basic_context.get_config("missing") is None
        assert basic_context.get_config("missing", "default") == "default"
    
    @pytest.mark.asyncio
    async def test_wait(self, basic_context: TaskContext):
        """验证 wait 方法。"""
        start = time.time()
        await basic_context.wait(0.1)
        elapsed = time.time() - start
        
        assert elapsed >= 0.1

    @pytest.mark.asyncio
    async def test_wait_raises_cancelled_error_when_stop_requested(self, basic_context: TaskContext):
        """验证 wait 在收到 stop 后会尽快中断。"""
        basic_context.logger = MagicMock()

        async def request_stop():
            await asyncio.sleep(0.05)
            basic_context.request_stop()

        stopper = asyncio.create_task(request_stop())
        start = time.time()
        with pytest.raises(asyncio.CancelledError):
            await basic_context.wait(1)
        elapsed = time.time() - start
        await stopper

        assert elapsed < 0.5
    
    @pytest.mark.asyncio
    async def test_screenshot_without_page_raises_error(self, basic_context: TaskContext):
        """验证没有 Page 时 screenshot 抛出错误。"""
        with pytest.raises(RuntimeError, match="Page 未初始化"):
            await basic_context.screenshot("test")
    
    @pytest.mark.asyncio
    async def test_screenshot_with_page(self, mock_context_with_page: TaskContext):
        """验证有 Page 时 screenshot 正常工作。"""
        path = await mock_context_with_page.screenshot("test_shot")
        
        assert "test_shot" in path
        assert path.endswith(".png")
        mock_context_with_page.page.screenshot.assert_called_once()

    @pytest.mark.asyncio
    async def test_screenshot_same_second_keeps_unique_filenames(
        self,
        monkeypatch,
        mock_context_with_page: TaskContext,
        tmp_path,
    ):
        """验证同秒连续截图不会互相覆盖。"""
        monkeypatch.chdir(tmp_path)
        timestamps = [
            datetime(2026, 4, 23, 12, 0, 0, 123456),
            datetime(2026, 4, 23, 12, 0, 0, 789012),
        ]

        class _FakeDateTime:
            @classmethod
            def now(cls):
                return timestamps.pop(0)

        monkeypatch.setattr(contracts_context, "datetime", _FakeDateTime)

        first_path = await mock_context_with_page.screenshot("test_shot")
        second_path = await mock_context_with_page.screenshot("test_shot")

        assert first_path != second_path
        assert (tmp_path / first_path).parent == tmp_path / "screenshots"
        assert (tmp_path / second_path).parent == tmp_path / "screenshots"
        assert Path(first_path).name.startswith("test_shot_20260423_120000_")
        assert Path(second_path).name.startswith("test_shot_20260423_120000_")
        assert mock_context_with_page.page.screenshot.call_args_list[0].kwargs["path"] == first_path
        assert mock_context_with_page.page.screenshot.call_args_list[1].kwargs["path"] == second_path


# === 停止/取消测试 ===

class TestTaskContextStopControl:
    """测试停止/取消控制。"""
    
    def test_should_stop_initially_false(self, basic_context: TaskContext):
        """验证初始状态不请求停止。"""
        assert basic_context.should_stop() is False
    
    def test_request_stop(self, basic_context: TaskContext):
        """验证请求停止。"""
        basic_context.logger = MagicMock()
        
        basic_context.request_stop()
        
        assert basic_context.should_stop() is True


class TestTaskContextSignals:
    """测试任务信号。"""

    def test_emit_signal_requires_allowed_phase(self, basic_context: TaskContext):
        with pytest.raises(RuntimeError, match="当前阶段不允许发出任务信号"):
            basic_context.emit_signal(TaskSignal.fail(message="失败"))

    def test_emit_signal_records_runtime_payload(self, basic_context: TaskContext):
        basic_context.set_signal_phase("run_module")

        signal = TaskSignal.wait_for_confirmation(
            message="等待人工确认",
            payload={"ticket_id": "T-1"},
            env_action=EnvAction.KEEP_ALIVE,
        )
        basic_context.emit_signal(signal)

        assert basic_context.get_signal() == signal
        assert basic_context.runtime["task_signal"]["action"] == "wait_for_confirmation"

    def test_clear_signal_removes_pending_signal(self, basic_context: TaskContext):
        basic_context.set_signal_phase("run_module")
        basic_context.emit_signal(TaskSignal.succeed(message="完成"))

        basic_context.clear_signal()

        assert basic_context.get_signal() is None
        assert "task_signal" not in basic_context.runtime


# === 子任务调用测试 ===

class TestTaskContextSubtask:
    """测试子任务调用。"""
    
    @pytest.mark.asyncio
    async def test_run_subtask_without_executor_raises_error(self, basic_context: TaskContext):
        """验证没有执行器时抛出错误。"""
        with pytest.raises(RuntimeError, match="子任务执行器未注入"):
            await basic_context.run_subtask("some_task")
    
    @pytest.mark.asyncio
    async def test_run_subtask_with_executor(self, basic_context: TaskContext):
        """验证有执行器时正常调用子任务。"""
        basic_context.logger = MagicMock()
        
        # 设置 Mock 执行器
        mock_result = TaskResult.ok(data={"result": "success"})
        mock_executor = AsyncMock(return_value=mock_result)
        basic_context._subtask_executor = mock_executor
        
        result = await basic_context.run_subtask("sub_task")
        
        assert result == {"result": "success"}
        mock_executor.assert_called_once_with("sub_task", basic_context)
    
    @pytest.mark.asyncio
    async def test_run_subtask_merges_kwargs_to_state(self, basic_context: TaskContext):
        """验证子任务参数合并到 state。"""
        basic_context.logger = MagicMock()
        basic_context._subtask_executor = AsyncMock(return_value=TaskResult.ok())

        await basic_context.run_subtask("sub_task", param1="value1", param2=123)

        assert basic_context.state["param1"] == "value1"
        assert basic_context.state["param2"] == 123

    @pytest.mark.asyncio
    async def test_run_subtask_returns_true_for_success_without_payload(self, basic_context: TaskContext):
        """验证成功但无 data 时返回 True，便于工作流按布尔语义判断。"""
        basic_context.logger = MagicMock()
        basic_context._subtask_executor = AsyncMock(return_value=TaskResult.ok())

        result = await basic_context.run_subtask("sub_task")

        assert result is True

    @pytest.mark.asyncio
    async def test_run_subtask_returns_false_for_failed_result(self, basic_context: TaskContext):
        """验证失败结果返回 falsey 的结构化 payload。"""
        basic_context.logger = MagicMock()
        basic_context._subtask_executor = AsyncMock(return_value=TaskResult.fail(message="failed"))

        result = await basic_context.run_subtask("sub_task")

        assert isinstance(result, dict)
        assert not result
        assert result["status"] == "failed"
        assert result["message"] == "failed"
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_run_subtask_preserves_failed_result_details(self, basic_context: TaskContext):
        """验证失败结果会保留 error 和原始 data。"""
        basic_context.logger = MagicMock()
        basic_context._subtask_executor = AsyncMock(
            return_value=TaskResult.fail(
                message="labor login failed",
                error="invalid_labor_credentials",
                data={"current_url": "https://frontend.lobaobao97.com/login"},
            )
        )

        result = await basic_context.run_subtask("sub_task")

        assert isinstance(result, dict)
        assert not result
        assert result["status"] == "failed"
        assert result["message"] == "labor login failed"
        assert result["error"] == "invalid_labor_credentials"
        assert result["current_url"] == "https://frontend.lobaobao97.com/login"

    @pytest.mark.asyncio
    async def test_run_subtask_raises_cancelled_error_when_stop_requested(self, basic_context: TaskContext):
        """验证 stop 后不会继续启动新的子任务。"""
        basic_context.logger = MagicMock()
        basic_context._subtask_executor = AsyncMock(return_value=TaskResult.ok())
        basic_context.request_stop()

        with pytest.raises(asyncio.CancelledError):
            await basic_context.run_subtask("sub_task")

        basic_context._subtask_executor.assert_not_called()


# === 状态共享测试 ===

class TestTaskContextState:
    """测试状态共享。"""
    
    def test_state_is_mutable_dict(self, basic_context: TaskContext):
        """验证 state 是可变字典。"""
        basic_context.state["phase"] = "login"
        basic_context.state["cursor"] = 100
        
        assert basic_context.state["phase"] == "login"
        assert basic_context.state["cursor"] == 100
    
