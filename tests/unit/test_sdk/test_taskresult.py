"""TaskResult 单元测试。

测试用例覆盖:
    - TC_SDK_009: 返回成功结果
    - TC_SDK_010: 返回失败结果
    - JSON 序列化/反序列化测试
"""

import json

from crawler4j_sdk import TaskResult


class TestTaskResultOk:
    """测试 TaskResult.ok 工厂方法。"""
    
    def test_ok_with_defaults(self):
        """TC_SDK_009: 验证默认成功结果。"""
        result = TaskResult.ok()
        
        assert result.success is True
        assert result.tasks_completed == 1
        assert result.message == "成功"
        assert result.data == {}
        assert result.error is None
    
    def test_ok_with_custom_params(self):
        """验证自定义参数。"""
        result = TaskResult.ok(
            tasks_completed=5,
            message="处理完成",
            data={"processed": 5}
        )
        
        assert result.success is True
        assert result.tasks_completed == 5
        assert result.message == "处理完成"
        assert result.data == {"processed": 5}
    
    def test_ok_with_kwargs(self):
        """验证 kwargs 合并到 data。"""
        result = TaskResult.ok(
            message="完成",
            data={"base": "value"},
            extra1="extra_value",
            extra2=123
        )
        
        assert result.data["base"] == "value"
        assert result.data["extra1"] == "extra_value"
        assert result.data["extra2"] == 123


class TestTaskResultFail:
    """测试 TaskResult.fail 工厂方法。"""
    
    def test_fail_basic(self):
        """TC_SDK_010: 验证基本失败结果。"""
        result = TaskResult.fail(message="操作失败")
        
        assert result.success is False
        assert result.tasks_completed == 0
        assert result.message == "操作失败"
        assert result.error is None
    
    def test_fail_with_error(self):
        """验证带错误详情的失败结果。"""
        result = TaskResult.fail(
            message="登录失败",
            error="验证码错误"
        )
        
        assert result.success is False
        assert result.message == "登录失败"
        assert result.error == "验证码错误"
    
    def test_fail_with_error_code(self):
        """验证带错误码的失败结果。"""
        result = TaskResult.fail(
            message="认证失败",
            error="Token 过期",
            error_code="SDK-AUTH-TOKEN-EXPIRED",
            retryable=True
        )
        
        assert result.success is False
        assert result.data["error_code"] == "SDK-AUTH-TOKEN-EXPIRED"
        assert result.data["retryable"] is True


class TestTaskResultSerialization:
    """测试 TaskResult 序列化。"""
    
    def test_to_dict(self):
        """验证 to_dict 方法。"""
        result = TaskResult.ok(
            tasks_completed=3,
            message="完成",
            data={"key": "value"}
        )
        
        d = result.to_dict()
        
        assert isinstance(d, dict)
        assert d["success"] is True
        assert d["tasks_completed"] == 3
        assert d["message"] == "完成"
        assert d["data"] == {"key": "value"}
        assert d["error"] is None
    
    def test_to_dict_json_serializable(self):
        """验证 to_dict 结果可 JSON 序列化。"""
        result = TaskResult.ok(
            message="测试",
            data={"nested": {"list": [1, 2, 3]}}
        )
        
        d = result.to_dict()
        json_str = json.dumps(d, ensure_ascii=False)
        
        assert isinstance(json_str, str)
        assert "测试" in json_str
    
    def test_from_dict(self):
        """验证 from_dict 方法。"""
        data = {
            "success": True,
            "tasks_completed": 10,
            "message": "批量完成",
            "data": {"processed": 10},
            "error": None
        }
        
        result = TaskResult.from_dict(data)
        
        assert result.success is True
        assert result.tasks_completed == 10
        assert result.message == "批量完成"
        assert result.data == {"processed": 10}
        assert result.error is None
    
    def test_from_dict_with_missing_fields(self):
        """验证 from_dict 处理缺失字段。"""
        data = {"success": False, "message": "失败"}
        
        result = TaskResult.from_dict(data)
        
        assert result.success is False
        assert result.message == "失败"
        assert result.tasks_completed == 0  # 默认值
        assert result.data == {}  # 默认值
        assert result.error is None  # 默认值
    
    def test_round_trip_serialization(self):
        """验证序列化/反序列化往返。"""
        original = TaskResult.fail(
            message="错误",
            error="详细错误信息",
            error_code="SDK-ERR-001"
        )
        
        # 序列化
        json_str = json.dumps(original.to_dict(), ensure_ascii=False)
        
        # 反序列化
        restored = TaskResult.from_dict(json.loads(json_str))
        
        assert restored.success == original.success
        assert restored.message == original.message
        assert restored.error == original.error
        assert restored.data == original.data


class TestTaskResultFields:
    """测试 TaskResult 字段。"""
    
    def test_default_values(self):
        """验证默认值。"""
        result = TaskResult()
        
        assert result.success is False
        assert result.tasks_completed == 0
        assert result.message == ""
        assert result.data == {}
        assert result.error is None
    
    def test_data_is_mutable(self):
        """验证 data 字段可修改。"""
        result = TaskResult.ok()
        result.data["new_key"] = "new_value"
        
        assert result.data["new_key"] == "new_value"
