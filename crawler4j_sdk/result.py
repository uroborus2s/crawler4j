"""TaskResult 任务执行结果模型。

本模块定义了 Crawler4j SDK 的核心契约之一：TaskResult（任务结果模型）。
TaskResult 是原子任务（TaskScript）的标准输出模型。

稳定契约 (Stable API - 同 MAJOR 版本内冻结):
    - 字段: success, tasks_completed, message, data, error
    - 工厂方法: ok, fail

参考规格: docs/srs/06-sdk/06-4-taskresult.md
"""

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class TaskResult:
    """任务执行结果模型。
    
    用于表示原子任务的执行结果，支持：
    - 成功/失败状态统一采集
    - UI/日志/监控的稳定解析
    - 后续持久化与追溯
    
    字段说明 (Stable):
        success: 是否成功。
        tasks_completed: 完成的任务/条目数量，用于进度/吞吐统计。
        message: 人类可读的结果信息，可直接展示在 UI。
        data: 结构化输出（业务数据、诊断字段、统计信息等）。
        error: 错误信息（失败时可填），给人看的错误细节。
    
    JSON 序列化形态:
        {
            "success": true,
            "tasks_completed": 1,
            "message": "成功",
            "data": {"foo": "bar"},
            "error": null
        }
    
    建议的 data 扩展字段 (向后兼容):
        - error_code: 稳定错误码，用于机器判定
        - retryable: 是否建议重试
        - duration_ms: 耗时（毫秒）
        - artifacts: 输出物引用（截图路径、日志片段 ID 等）
    
    脱敏规则:
        - data 与 error 中不得出现密码、Cookie、Token 等机密
        - 手机号/身份证/订单号等敏感信息应掩码处理
    
    示例:
        >>> # 成功结果
        >>> result = TaskResult.ok(
        ...     tasks_completed=5,
        ...     message="处理完成",
        ...     data={"processed": 5, "skipped": 0}
        ... )
        >>> 
        >>> # 失败结果
        >>> result = TaskResult.fail(
        ...     message="登录失败",
        ...     error="验证码识别错误",
        ...     error_code="SDK-AUTH-CAPTCHA",
        ...     retryable=True
        ... )
        >>> 
        >>> # JSON 序列化
        >>> json_dict = result.to_dict()
    """
    
    # === 稳定字段 ===
    
    success: bool = False
    """是否成功。"""
    
    tasks_completed: int = 0
    """完成的任务/条目数量，用于进度/吞吐统计。"""
    
    message: str = ""
    """人类可读的结果信息，可直接展示在 UI。"""
    
    data: dict[str, Any] = field(default_factory=dict)
    """结构化输出。业务数据、诊断字段、统计信息等，必须 JSON 可序列化。"""
    
    error: str | None = None
    """错误信息（失败时可填），给人看的错误细节。"""
    
    # === 工厂方法 (Stable) ===
    
    @classmethod
    def ok(
        cls,
        tasks_completed: int = 1,
        message: str = "成功",
        data: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> "TaskResult":
        """创建成功结果。
        
        Args:
            tasks_completed: 完成数量，默认 1。
            message: 结果消息，默认 "成功"。
            data: 结构化业务数据，会与 kwargs 合并。
            **kwargs: 额外结构化字段，会合并进 data。
        
        Returns:
            TaskResult: 成功状态的结果对象。
        
        Example:
            >>> result = TaskResult.ok(
            ...     tasks_completed=10,
            ...     message="批量处理完成",
            ...     data={"total": 10},
            ...     processed=10,
            ...     duration_ms=1234
            ... )
        """
        payload: dict[str, Any] = {}
        if data:
            payload.update(data)
        if kwargs:
            payload.update(kwargs)
        return cls(
            success=True,
            tasks_completed=tasks_completed,
            message=message,
            data=payload,
        )
    
    @classmethod
    def fail(
        cls,
        message: str,
        error: str | None = None,
        data: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> "TaskResult":
        """创建失败结果。
        
        Args:
            message: 结果消息（必填），给人看的短句。
            error: 错误详情（可选），给人看的错误细节。
            data: 结构化业务数据/诊断字段，会与 kwargs 合并。
            **kwargs: 额外结构化字段，会合并进 data。
                      建议包含 error_code（稳定错误码）和 retryable（是否可重试）。
        
        Returns:
            TaskResult: 失败状态的结果对象。
        
        Example:
            >>> result = TaskResult.fail(
            ...     message="登录失败",
            ...     error="验证码识别错误，已重试3次",
            ...     error_code="SDK-AUTH-CAPTCHA",
            ...     retryable=True,
            ...     artifacts={"screenshot": "/path/to/error.png"}
            ... )
        """
        payload: dict[str, Any] = {}
        if data:
            payload.update(data)
        if kwargs:
            payload.update(kwargs)
        return cls(
            success=False,
            tasks_completed=0,
            message=message,
            data=payload,
            error=error,
        )
    
    # === 序列化方法 ===
    
    def to_dict(self) -> dict[str, Any]:
        """序列化为字典，用于 JSON 输出。
        
        Returns:
            dict: 包含所有稳定字段的字典，可直接 json.dumps()。
        
        Example:
            >>> result = TaskResult.ok(message="完成")
            >>> import json
            >>> json_str = json.dumps(result.to_dict(), ensure_ascii=False)
        """
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskResult":
        """从字典反序列化创建 TaskResult。
        
        Args:
            data: 包含 TaskResult 字段的字典。
        
        Returns:
            TaskResult: 反序列化后的结果对象。
        
        Example:
            >>> data = {"success": True, "message": "OK", "data": {}}
            >>> result = TaskResult.from_dict(data)
        """
        return cls(
            success=data.get("success", False),
            tasks_completed=data.get("tasks_completed", 0),
            message=data.get("message", ""),
            data=data.get("data", {}),
            error=data.get("error"),
        )
