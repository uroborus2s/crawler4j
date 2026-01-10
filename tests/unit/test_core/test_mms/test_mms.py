"""MMS 数据模型单元测试。"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.core.mms.models import (
    ModuleInfo,
    ModuleManifest,
    ModuleSource,
    ModuleStatus,
    WorkflowInfo,
)
from src.core.mms.scanner import ModuleScanner


class TestModuleManifest:
    """测试 ModuleManifest。"""
    
    def test_from_dict(self):
        """测试从字典反序列化。"""
        data = {
            "name": "test_module",
            "version": "1.0.0",
            "display_name": "测试模块",
            "workflows": [
                {
                    "name": "login_flow",
                    "display_name": "登录流程",
                }
            ],
        }
        
        manifest = ModuleManifest.from_dict(data)
        
        assert manifest.name == "test_module"
        assert manifest.version == "1.0.0"
        assert len(manifest.workflows) == 1
        assert manifest.workflows[0].name == "login_flow"
    
    def test_to_dict(self):
        """测试序列化。"""
        manifest = ModuleManifest(
            name="test_module",
            workflows=[WorkflowInfo(name="flow1")],
        )
        
        data = manifest.to_dict()
        
        assert data["name"] == "test_module"
        assert len(data["workflows"]) == 1


class TestModuleScanner:
    """测试 ModuleScanner。"""
    
    def test_discover_empty_dirs(self, tmp_path):
        """测试空目录发现。"""
        scanner = ModuleScanner(scan_paths=[tmp_path])
        
        result = scanner.discover()
        
        assert result == []
    
    def test_discover_valid_module(self, tmp_path):
        """测试发现有效模块。"""
        # 创建模块目录
        module_dir = tmp_path / "my_module"
        module_dir.mkdir()
        
        # 创建 module.yaml
        manifest_path = module_dir / "module.yaml"
        manifest_path.write_text("name: my_module\nversion: 1.0.0")
        
        scanner = ModuleScanner(scan_paths=[tmp_path])
        
        result = scanner.discover()
        
        assert len(result) == 1
        assert result[0][0] == module_dir
    
    def test_ignore_pycache(self, tmp_path):
        """测试忽略 __pycache__。"""
        pycache = tmp_path / "__pycache__"
        pycache.mkdir()
        (pycache / "module.yaml").write_text("name: invalid")
        
        scanner = ModuleScanner(scan_paths=[tmp_path])
        
        result = scanner.discover()
        
        assert result == []
    
    def test_parse_manifest(self, tmp_path):
        """测试解析 manifest。"""
        module_dir = tmp_path / "test_module"
        module_dir.mkdir()
        
        manifest_content = """
name: test_module
version: 2.0.0
display_name: 测试模块
workflows:
  - name: main_flow
    display_name: 主流程
"""
        (module_dir / "module.yaml").write_text(manifest_content)
        
        scanner = ModuleScanner(scan_paths=[tmp_path])
        
        manifest = scanner.parse_manifest(module_dir)
        
        assert manifest.name == "test_module"
        assert manifest.version == "2.0.0"
        assert len(manifest.workflows) == 1
    
    def test_validate_missing_name(self, tmp_path):
        """测试校验缺少 name。"""
        from src.core.mms.models import ModuleValidationError
        
        manifest = ModuleManifest(name="")
        scanner = ModuleScanner(scan_paths=[tmp_path])
        
        with pytest.raises(ModuleValidationError) as exc_info:
            scanner.validate(manifest, tmp_path)
        
        assert "name" in str(exc_info.value)
    
    def test_load_module_success(self, tmp_path):
        """测试成功加载模块。"""
        module_dir = tmp_path / "good_module"
        module_dir.mkdir()
        
        manifest_content = """
name: good_module
version: 1.0.0
"""
        (module_dir / "module.yaml").write_text(manifest_content)
        
        scanner = ModuleScanner(scan_paths=[tmp_path])
        
        module_info = scanner.load_module(module_dir, ModuleSource.EXTERNAL)
        
        assert module_info.name == "good_module"
        assert module_info.status == ModuleStatus.ENABLED
    
    def test_load_module_invalid(self, tmp_path):
        """测试加载无效模块。"""
        module_dir = tmp_path / "bad_module"
        module_dir.mkdir()
        # 不创建 module.yaml
        
        scanner = ModuleScanner(scan_paths=[tmp_path])
        
        module_info = scanner.load_module(module_dir, ModuleSource.EXTERNAL)
        
        assert module_info.status == ModuleStatus.INVALID
        assert module_info.error != ""
