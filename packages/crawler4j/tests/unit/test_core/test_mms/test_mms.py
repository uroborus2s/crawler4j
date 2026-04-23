"""MMS 数据模型单元测试。"""

import pytest

from src.core.mms.models import (
    ConfigDefaultsInfo,
    ModuleManifest,
    ModuleSource,
    ModuleStatus,
    UpgradeSourceInfo,
    UIPageInfo,
    UIExtensionInfo,
    WorkflowInfo,
)
from src.core.mms.scanner import ModuleScanner


def _empty_data_contract() -> dict[str, list[dict[str, object]]]:
    return {"resources": [], "views": [], "queries": [], "seeds": []}


class TestModuleManifest:
    """测试 ModuleManifest。"""
    
    def test_from_dict(self):
        """测试从字典反序列化。"""
        data = {
            "name": "test_module",
            "runtime_api": "core-native-v1",
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
                "pages": [
                    {
                        "id": "dashboard",
                        "icon": "📊",
                        "label": "今日运营看板",
                    },
                    {
                        "id": "accounts",
                        "icon": "📋",
                        "label": "账号管理",
                    },
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
            "default_workflow": "login_flow",
            "data": _empty_data_contract(),
        }
        
        manifest = ModuleManifest.from_dict(data)
        
        assert manifest.name == "test_module"
        assert manifest.version == "1.0.0"
        assert len(manifest.workflows) == 1
        assert manifest.workflows[0].name == "login_flow"
        assert manifest.upgrade_source.repo == "example/test_module"
        assert [page.id for page in manifest.ui_extension.pages] == ["dashboard", "accounts"]
        assert manifest.config_defaults.module == {"base_url": "https://example.com"}
        assert manifest.config_defaults.workflows == {"login_flow": {"headless": False}}
        assert manifest.data == _empty_data_contract()
    
    def test_to_dict(self):
        """测试序列化。"""
        manifest = ModuleManifest(
            name="test_module",
            runtime_api="core-native-v1",
            upgrade_source=UpgradeSourceInfo(repo="example/test_module"),
            workflows=[WorkflowInfo(name="flow1")],
            default_workflow="flow1",
            ui_extension=UIExtensionInfo(
                pages=[
                    UIPageInfo(
                        id="dashboard",
                        icon="📊",
                        label="今日运营看板",
                    ),
                    UIPageInfo(
                        id="accounts",
                        icon="📋",
                        label="账号管理",
                    ),
                ],
            ),
            config_defaults=ConfigDefaultsInfo(
                module={"base_url": "https://example.com"},
                workflows={"flow1": {"headless": False}},
            ),
            data=_empty_data_contract(),
        )
        
        data = manifest.to_dict()

        assert data["name"] == "test_module"
        assert data["runtime_api"] == "core-native-v1"
        assert len(data["workflows"]) == 1
        assert data["upgrade_source"] == {
            "type": "github_release",
            "repo": "example/test_module",
            "allow_prerelease": False,
        }
        assert data["ui_extension"]["pages"] == [
            {
                "id": "dashboard",
                "icon": "📊",
                "label": "今日运营看板",
            },
            {
                "id": "accounts",
                "icon": "📋",
                "label": "账号管理",
            },
        ]
        assert data["config_defaults"] == {
            "module": {"base_url": "https://example.com"},
            "workflows": {"flow1": {"headless": False}},
        }
        assert data["default_workflow"] == "flow1"
        assert data["data"] == _empty_data_contract()


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
runtime_api: core-native-v1
version: 2.0.0
display_name: 测试模块
upgrade_source:
  type: github_release
  repo: example/test_module
workflows:
  - name: main_flow
    display_name: 主流程
default_workflow: main_flow
data:
  resources: []
  views: []
  queries: []
  seeds: []
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
runtime_api: core-native-v1
upgrade_source:
  type: github_release
  repo: example/test_module
workflows:
  - name: default
default_workflow: default
config_defaults:
  module:
    base_url: https://example.com
  workflows:
    default:
      headless: false
data:
  resources: []
  views: []
  queries: []
  seeds: []
""".strip(),
            encoding="utf-8",
        )

        scanner = ModuleScanner(scan_paths=[tmp_path])
        manifest = scanner.parse_manifest(module_dir)

        assert manifest.config_defaults.module == {"base_url": "https://example.com"}
        assert manifest.config_defaults.workflows == {"default": {"headless": False}}

    def test_parse_manifest_rejects_unsupported_ui_extension_fields(self, tmp_path):
        from src.core.mms.models import ModuleParseError

        module_dir = tmp_path / "test_module"
        module_dir.mkdir()
        (module_dir / "module.yaml").write_text(
            """
name: test_module
runtime_api: core-native-v1
version: 1.0.0
upgrade_source:
  type: github_release
  repo: example/test_module
ui_extension:
  extra: unsupported
workflows:
  - name: default
default_workflow: default
data:
  resources: []
  views: []
  queries: []
  seeds: []
""".strip(),
            encoding="utf-8",
        )

        scanner = ModuleScanner(scan_paths=[tmp_path])

        with pytest.raises(ModuleParseError) as exc_info:
            scanner.parse_manifest(module_dir)

        assert "ui_extension" in str(exc_info.value)
    
    def test_validate_missing_name(self, tmp_path):
        """测试校验缺少 name。"""
        from src.core.mms.models import ModuleValidationError
        
        manifest = ModuleManifest(
            name="",
            runtime_api="core-native-v1",
            workflows=[WorkflowInfo(name="default")],
            default_workflow="default",
            upgrade_source=UpgradeSourceInfo(repo="example/test_module"),
            data=_empty_data_contract(),
        )
        scanner = ModuleScanner(scan_paths=[tmp_path])
        
        with pytest.raises(ModuleValidationError) as exc_info:
            scanner.validate(manifest, tmp_path)

        assert "name" in str(exc_info.value)

    def test_validate_requires_upgrade_source(self, tmp_path):
        from src.core.mms.models import ModuleValidationError

        manifest = ModuleManifest(
            name="demo_module",
            runtime_api="core-native-v1",
            workflows=[WorkflowInfo(name="default")],
            default_workflow="default",
            data=_empty_data_contract(),
        )
        scanner = ModuleScanner(scan_paths=[tmp_path])

        with pytest.raises(ModuleValidationError) as exc_info:
            scanner.validate(manifest, tmp_path)

        assert "upgrade_source" in str(exc_info.value)

    def test_validate_rejects_non_canonical_upgrade_repo(self, tmp_path):
        from src.core.mms.models import ModuleValidationError

        manifest = ModuleManifest(
            name="demo_module",
            runtime_api="core-native-v1",
            workflows=[WorkflowInfo(name="default")],
            default_workflow="default",
            upgrade_source=UpgradeSourceInfo(repo="https://github.com/example/demo_module"),
            data=_empty_data_contract(),
        )
        scanner = ModuleScanner(scan_paths=[tmp_path])

        with pytest.raises(ModuleValidationError) as exc_info:
            scanner.validate(manifest, tmp_path)

        assert "owner/repo" in str(exc_info.value)

    def test_validate_rejects_invalid_semver_version(self, tmp_path):
        from src.core.mms.models import ModuleValidationError

        manifest = ModuleManifest(
            name="demo_module",
            runtime_api="core-native-v1",
            version="1.0",
            workflows=[WorkflowInfo(name="default")],
            default_workflow="default",
            upgrade_source=UpgradeSourceInfo(repo="example/demo_module"),
            data=_empty_data_contract(),
        )
        scanner = ModuleScanner(scan_paths=[tmp_path])

        with pytest.raises(ModuleValidationError) as exc_info:
            scanner.validate(manifest, tmp_path)

        assert "语义化版本" in str(exc_info.value)
    
    def test_load_module_success(self, tmp_path):
        """测试成功加载模块。"""
        module_dir = tmp_path / "good_module"
        module_dir.mkdir()
        
        manifest_content = """
name: good_module
runtime_api: core-native-v1
version: 1.0.0
upgrade_source:
  type: github_release
  repo: example/good_module
workflows:
  - name: default
default_workflow: default
data:
  resources: []
  views: []
  queries: []
  seeds: []
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

    def test_validate_allows_additional_module_files(self, tmp_path):
        (tmp_path / "config_schema.json").write_text("{}", encoding="utf-8")
        manifest = ModuleManifest(
            name="demo_module",
            runtime_api="core-native-v1",
            workflows=[WorkflowInfo(name="default")],
            default_workflow="default",
            upgrade_source=UpgradeSourceInfo(repo="example/demo_module"),
            data=_empty_data_contract(),
        )
        scanner = ModuleScanner(scan_paths=[tmp_path])

        assert scanner.validate(manifest, tmp_path) == []

    def test_validate_rejects_unsupported_page_extra_field(self):
        manifest = ModuleManifest(
            name="demo_module",
            upgrade_source=UpgradeSourceInfo(repo="example/demo_module"),
            ui_extension=UIExtensionInfo(
                pages=[
                    UIPageInfo(id="custom_page", label="自定义页面")
                ],
            ),
        )
        manifest_dict = manifest.to_dict()
        manifest_dict["ui_extension"]["pages"][0]["extra"] = "unsupported"
        with pytest.raises(ValueError):
            ModuleManifest.from_dict(manifest_dict)

    def test_validate_rejects_unknown_workflow_in_config_defaults(self, tmp_path):
        from src.core.mms.models import ModuleValidationError

        manifest = ModuleManifest.from_dict(
            {
                "name": "demo_module",
                "runtime_api": "core-native-v1",
                "upgrade_source": {
                    "type": "github_release",
                    "repo": "example/demo_module",
                },
                "workflows": [{"name": "default"}],
                "default_workflow": "default",
                "config_defaults": {
                    "workflows": {
                        "missing_workflow": {
                            "headless": False,
                        }
                    }
                },
                "data": _empty_data_contract(),
            }
        )
        scanner = ModuleScanner(scan_paths=[tmp_path])

        with pytest.raises(ModuleValidationError) as exc_info:
            scanner.validate(manifest, tmp_path)

        assert "missing_workflow" in str(exc_info.value)
