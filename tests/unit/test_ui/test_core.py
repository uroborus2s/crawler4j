"""UI Core 集成单元测试。"""

import pytest

from src.ui.core.command_channel import (
    CommandChannel,
    CommandResponse,
    CommandResult,
)
from src.ui.core.event_bus import (
    Event,
    EventBus,
    EventType,
)


class TestCommandChannel:
    """测试 CommandChannel。"""
    
    def test_register_and_execute(self):
        """测试注册并执行命令。"""
        channel = CommandChannel()
        
        def handler(x: int, y: int) -> int:
            return x + y
        
        channel.register("math.add", handler)
        
        response = channel.execute("math.add", {"x": 2, "y": 3})
        
        assert response.result == CommandResult.SUCCESS
        assert response.data == 5
    
    def test_command_not_found(self):
        """测试命令不存在。"""
        channel = CommandChannel()
        
        response = channel.execute("unknown.command")
        
        assert response.result == CommandResult.ERROR
        assert response.code == "COMMAND_NOT_FOUND"
    
    def test_execution_error(self):
        """测试执行错误。"""
        channel = CommandChannel()
        
        def error_handler():
            raise ValueError("test error")
        
        channel.register("will.fail", error_handler)
        
        response = channel.execute("will.fail")
        
        assert response.result == CommandResult.ERROR
        assert "test error" in response.message


class TestCommandResponse:
    """测试 CommandResponse。"""
    
    def test_success(self):
        """测试成功响应。"""
        response = CommandResponse.success(data={"count": 10})
        
        assert response.result == CommandResult.SUCCESS
        assert response.data == {"count": 10}
    
    def test_error(self):
        """测试错误响应。"""
        response = CommandResponse.error(
            code="ERR_001",
            message="出错了",
            hint="请重试",
        )
        
        assert response.result == CommandResult.ERROR
        assert response.code == "ERR_001"
        assert response.hint == "请重试"


class TestEventBus:
    """测试 EventBus。"""
    
    def test_subscribe_and_publish(self, qtbot):
        """测试订阅和发布。"""
        bus = EventBus()
        received = []
        
        def handler(event: Event):
            received.append(event)
        
        bus.subscribe(EventType.TASK_STARTED, handler)
        
        event = Event(type=EventType.TASK_STARTED, task_run_id="task-1")
        bus.publish(event)
        
        # 等待信号传递
        qtbot.wait(50)
        
        assert len(received) == 1
        assert received[0].task_run_id == "task-1"
    
    def test_subscribe_by_module(self, qtbot):
        """测试按模块订阅。"""
        bus = EventBus()
        received = []
        
        def handler(event: Event):
            received.append(event)
        
        bus.subscribe_by_module("ctrip", handler)
        
        # 发布 ctrip 模块事件
        bus.publish(Event(type=EventType.MODULE_ENABLED, module_name="ctrip"))
        
        # 发布其他模块事件（不应接收）
        bus.publish(Event(type=EventType.MODULE_ENABLED, module_name="labor"))
        
        qtbot.wait(50)
        
        assert len(received) == 1
        assert received[0].module_name == "ctrip"
    
    def test_subscribe_by_task(self, qtbot):
        """测试按任务订阅。"""
        bus = EventBus()
        received = []
        
        def handler(event: Event):
            received.append(event)
        
        bus.subscribe_by_task("task-123", handler)
        
        bus.publish(Event(type=EventType.TASK_PROGRESS, task_run_id="task-123"))
        bus.publish(Event(type=EventType.TASK_PROGRESS, task_run_id="task-456"))
        
        qtbot.wait(50)
        
        assert len(received) == 1
        assert received[0].task_run_id == "task-123"
    
    def test_unsubscribe(self, qtbot):
        """测试取消订阅。"""
        bus = EventBus()
        received = []
        
        def handler(event: Event):
            received.append(event)
        
        bus.subscribe(EventType.TASK_FINISHED, handler)
        bus.unsubscribe(EventType.TASK_FINISHED, handler)
        
        bus.publish(Event(type=EventType.TASK_FINISHED))
        
        qtbot.wait(50)
        
        assert len(received) == 0


class TestEvent:
    """测试 Event 数据类。"""
    
    def test_default_values(self):
        """测试默认值。"""
        event = Event(type=EventType.TASK_STARTED)
        
        assert event.type == EventType.TASK_STARTED
        assert event.data == {}
        assert event.event_id is not None
        assert event.timestamp > 0
