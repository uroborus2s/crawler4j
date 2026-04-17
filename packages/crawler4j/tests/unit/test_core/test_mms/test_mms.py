"""MMS 数据模型单元测试。"""

import pytest

from src.core.mms.models import (
    ConfigDefaultsInfo,
    DetailMenuItem,
    ModuleManifest,
    ModuleSource,
    ModuleStatus,
    UpgradeSourceInfo,
    UIExtensionInfo,
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
            "upgrade_source": {
                "type": "github_release",
                "repo": "example/test_module",
            },
            "workflows": [
                {
                    "name": "login_flow",
                    "display_name": "登录流程",
                }
            ],
            "ui_extension": {
                "type": "micro_app",
                "entry": "ui:AccountConfigPage",
                "trusted": True,
                "detail_menu": [
                    {
                        "id": "accounts",
                        "label": "账号管理",
                        "entry": "core:data_table:accounts",
                    }
                ],
            },
            "config_defaults": {
                "module": {
                    "base_url": "https://example.com",
                },
                "workflows": {
                    "login_flow": {
                        "headless": False,
                    }
                },
            },
        }
        
        manifest = ModuleManifest.from_dict(data)
        
        assert manifest.name == "test_module"
        assert manifest.version == "1.0.0"
        assert len(manifest.workflows) == 1
        assert manifest.workflows[0].name == "login_flow"
        assert manifest.upgrade_source.repo == "example/test_module"
        assert manifest.ui_extension.type == "micro_app"
        assert manifest.ui_extension.trusted is True
        assert manifest.ui_extension.entry == "ui:AccountConfigPage"
        assert manifest.ui_extension.detail_menu[0].entry == "core:data_table:accounts"
        assert manifest.config_defaults.module == {"base_url": "https://example.com"}
        assert manifest.config_defaults.workflows == {"login_flow": {"headless": False}}
    
    def test_to_dict(self):
        """测试序列化。"""
        manifest = ModuleManifest(
            name="test_module",
            upgrade_source=UpgradeSourceInfo(repo="example/test_module"),
            workflows=[WorkflowInfo(name="flow1")],
            ui_extension=UIExtensionInfo(
                type="micro_app",
                entry="ui:AccountConfigPage",
                trusted=True,
                detail_menu=[DetailMenuItem(id="accounts", entry="core:data_table:accounts")],
            ),
            config_defaults=ConfigDefaultsInfo(
                module={"base_url": "https://example.com"},
                workflows={"flow1": {"headless": False}},
            ),
        )
        
        data = manifest.to_dict()

        assert data["name"] == "test_module"
        assert len(data["workflows"]) == 1
        assert data["upgrade_source"] == {
            "type": "github_release",
            "repo": "example/test_module",
            "allow_prerelease": False,
        }
        assert data["ui_extension"]["trusted"] is True
        assert data["ui_extension"]["entry"] == "ui:AccountConfigPage"
        assert data["ui_extension"]["detail_menu"][0]["entry"] == "core:data_table:accounts"
        assert data["config_defaults"] == {
            "module": {"base_url": "https://example.com"},
            "workflows": {"flow1": {"headless": False}},
        }


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
        manifest_path.write_text(
            "name: my_module\n"
            "version: 1.0.0\n"
            "upgrade_source:\n"
            "  type: github_release\n"
            "  repo: example/my_module\n"
        )
        
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
upgrade_source:
  type: github_release
  repo: example/test_module
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

    def test_parse_manifest_rejects_removed_sdk_version_range(self, tmp_path):
        from src.core.mms.models import ModuleParseError

        module_dir = tmp_path / "test_module"
        module_dir.mkdir()
        (module_dir / "module.yaml").write_text(
            "name: test_module\nsdk_version_range: \">=9.9.9\"\n",
            encoding="utf-8",
        )

        scanner = ModuleScanner(scan_paths=[tmp_path])

        with pytest.raises(ModuleParseError) as exc_info:
            scanner.parse_manifest(module_dir)

        assert "sdk_version_range" in str(exc_info.value)

    def test_parse_manifest_reads_config_defaults(self, tmp_path):
        module_dir = tmp_path / "test_module"
        module_dir.mkdir()
        (module_dir / "module.yaml").write_text(
            """
name: test_module
upgrade_source:
  type: github_release
  repo: example/test_module
workflows:
  - name: default
config_defaults:
  module:
    base_url: https://example.com
  workflows:
    default:
      headless: false
""".strip(),
            encoding="utf-8",
        )

        scanner = ModuleScanner(scan_paths=[tmp_path])
        manifest = scanner.parse_manifest(module_dir)

        assert manifest.config_defaults.module == {"base_url": "https://example.com"}
        assert manifest.config_defaults.workflows == {"default": {"headless": False}}
    
    def test_validate_missing_name(self, tmp_path):
        """测试校验缺少 name。"""
        from src.core.mms.models import ModuleValidationError
        
        manifest = ModuleManifest(name="", upgrade_source=UpgradeSourceInfo(repo="example/test_module"))
        scanner = ModuleScanner(scan_paths=[tmp_path])
        
        with pytest.raises(ModuleValidationError) as exc_info:
            scanner.validate(manifest, tmp_path)

        assert "name" in str(exc_info.value)

    def test_validate_requires_upgrade_source(self, tmp_path):
        from src.core.mms.models import ModuleValidationError

        manifest = ModuleManifest(name="demo_module")
        scanner = ModuleScanner(scan_paths=[tmp_path])

        with pytest.raises(ModuleValidationError) as exc_info:
            scanner.validate(manifest, tmp_path)

        assert "upgrade_source" in str(exc_info.value)

    def test_validate_rejects_non_canonical_upgrade_repo(self, tmp_path):
        from src.core.mms.models import ModuleValidationError

        manifest = ModuleManifest(
            name="demo_module",
            upgrade_source=UpgradeSourceInfo(repo="https://github.com/example/demo_module"),
        )
        scanner = ModuleScanner(scan_paths=[tmp_path])

        with pytest.raises(ModuleValidationError) as exc_info:
            scanner.validate(manifest, tmp_path)

        assert "owner/repo" in str(exc_info.value)
    
    def test_load_module_success(self, tmp_path):
        """测试成功加载模块。"""
        module_dir = tmp_path / "good_module"
        module_dir.mkdir()
        
        manifest_content = """
name: good_module
version: 1.0.0
upgrade_source:
  type: github_release
  repo: example/good_module
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

    def test_validate_rejects_legacy_config_schema_and_unmanaged_detail_menu(self, tmp_path):
        from src.core.mms.models import ModuleValidationError

        (tmp_path / "config_schema.json").write_text("{}", encoding="utf-8")
        manifest = ModuleManifest(
            name="demo_module",
            upgrade_source=UpgradeSourceInfo(repo="example/demo_module"),
            ui_extension=UIExtensionInfo(
                detail_menu=[DetailMenuItem(id="custom_page", entry="ui:CustomPage")],
            ),
        )
        scanner = ModuleScanner(scan_paths=[tmp_path])

        with pytest.raises(ModuleValidationError) as exc_info:
            scanner.validate(manifest, tmp_path)

        assert "config_schema.json" in str(exc_info.value) or "detail_menu.entry" in str(exc_info.value)

    def test_validate_rejects_unknown_workflow_in_config_defaults(self, tmp_path):
        from src.core.mms.models import ModuleValidationError

        manifest = ModuleManifest.from_dict(
            {
                "name": "demo_module",
                "upgrade_source": {
                    "type": "github_release",
                    "repo": "example/demo_module",
                },
                "workflows": [{"name": "default"}],
                "config_defaults": {
                    "workflows": {
                        "missing_workflow": {
                            "headless": False,
                        }
                    }
                },
            }
        )
        scanner = ModuleScanner(scan_paths=[tmp_path])

        with pytest.raises(ModuleValidationError) as exc_info:
            scanner.validate(manifest, tmp_path)

        assert "missing_workflow" in str(exc_info.value)
