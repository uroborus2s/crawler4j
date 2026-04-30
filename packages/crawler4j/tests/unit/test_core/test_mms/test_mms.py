"""MMS 数据模型单元测试。"""

import pytest

from src.core.mms.models import (
    ConfigDefaultsInfo,
    ModuleManifest,
    ResourcePoolInfo,
    ModuleSource,
    ModuleStatus,
    UpgradeSourceInfo,
    UIPageInfo,
    UIExtensionInfo,
    WorkflowInfo,
    WorkflowParameterInfo,
    WorkflowParameterOptionInfo,
)
from src.core.mms.scanner import ModuleScanner


def _empty_data_contract() -> dict[str, list[dict[str, object]]]:
    return {"resources": [], "views": [], "queries": [], "seeds": []}


def _write_v2_runtime_package(module_dir) -> None:
    module_dir.mkdir(parents=True, exist_ok=True)
    (module_dir / "__init__.py").write_text("", encoding="utf-8")
    for package_name in ("interfaces", "objects", "workflows", "tasks", "data"):
        package_dir = module_dir / package_name
        package_dir.mkdir(exist_ok=True)
        (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (module_dir / "workflows" / "default.py").write_text(
        "from crawler4j_contracts import workflow\n\n"
        "@workflow(name='default')\n"
        "class DefaultWorkflow:\n"
        "    pass\n",
        encoding="utf-8",
    )


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
                    "tasks": ["login_task"],
                    "parameters": [
                        {
                            "name": "member_tier",
                            "label": "会员类型",
                            "type": "enum",
                            "required": True,
                            "default": "normal",
                            "options": [
                                {"label": "普通会员", "value": "normal"},
                                {"label": "高级会员", "value": "premium"},
                            ],
                        },
                        {
                            "name": "min_member_days",
                            "label": "会员天数下限",
                            "type": "integer",
                            "default": 30,
                            "min": 0,
                            "max": 365,
                            "step": 1,
                        },
                    ],
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
            "resource_pools": [
                {
                    "name": "bound_account_ready",
                    "display_name": "已绑定账号环境池",
                    "description": "可复用的已绑定账号环境",
                }
            ],
            "default_workflow": "login_flow",
            "data": _empty_data_contract(),
        }
        
        manifest = ModuleManifest.from_dict(data)
        
        assert manifest.name == "test_module"
        assert manifest.version == "1.0.0"
        assert len(manifest.workflows) == 1
        assert manifest.workflows[0].name == "login_flow"
        assert manifest.workflows[0].tasks == ["login_task"]
        assert manifest.workflows[0].parameters == [
            WorkflowParameterInfo(
                name="member_tier",
                label="会员类型",
                type="enum",
                required=True,
                default="normal",
                options=[
                    WorkflowParameterOptionInfo(label="普通会员", value="normal"),
                    WorkflowParameterOptionInfo(label="高级会员", value="premium"),
                ],
            ),
            WorkflowParameterInfo(
                name="min_member_days",
                label="会员天数下限",
                type="integer",
                default=30,
                min=0,
                max=365,
                step=1,
            ),
        ]
        assert manifest.upgrade_source.repo == "example/test_module"
        assert [page.id for page in manifest.ui_extension.pages] == ["dashboard", "accounts"]
        assert manifest.config_defaults.module == {"base_url": "https://example.com"}
        assert manifest.config_defaults.workflows == {"login_flow": {"headless": False}}
        assert manifest.resource_pools == [
            ResourcePoolInfo(
                name="bound_account_ready",
                display_name="已绑定账号环境池",
                description="可复用的已绑定账号环境",
            )
        ]
        assert manifest.data == _empty_data_contract()
    
    def test_to_dict(self):
        """测试序列化。"""
        manifest = ModuleManifest(
            name="test_module",
            runtime_api="core-native-v1",
            upgrade_source=UpgradeSourceInfo(repo="example/test_module"),
            workflows=[
                WorkflowInfo(
                    name="flow1",
                    tasks=["example_task"],
                    parameters=[
                        WorkflowParameterInfo(
                            name="member_tier",
                            label="会员类型",
                            type="enum",
                            required=True,
                            default="normal",
                            options=[
                                WorkflowParameterOptionInfo(label="普通会员", value="normal"),
                            ],
                        ),
                    ],
                )
            ],
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
            resource_pools=[
                ResourcePoolInfo(
                    name="bound_account_ready",
                    display_name="已绑定账号环境池",
                    description="可复用的已绑定账号环境",
                )
            ],
            data=_empty_data_contract(),
        )
        
        data = manifest.to_dict()

        assert data["name"] == "test_module"
        assert data["runtime_api"] == "core-native-v1"
        assert len(data["workflows"]) == 1
        assert data["workflows"][0]["tasks"] == ["example_task"]
        assert data["workflows"][0]["parameters"] == [
            {
                "name": "member_tier",
                "label": "会员类型",
                "type": "enum",
                "required": True,
                "default": "normal",
                "options": [{"label": "普通会员", "value": "normal"}],
            }
        ]
        assert "entry_class" not in data["workflows"][0]
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
        assert data["resource_pools"] == [
            {
                "name": "bound_account_ready",
                "display_name": "已绑定账号环境池",
                "description": "可复用的已绑定账号环境",
            }
        ]
        assert data["default_workflow"] == "flow1"
        assert data["data"] == _empty_data_contract()

    def test_from_dict_rejects_removed_workflow_entry_class(self):
        """旧 workflows[].entry_class 入口不再是 manifest 兼容面。"""
        data = {
            "name": "test_module",
            "runtime_api": "core-native-v1",
            "version": "1.0.0",
            "upgrade_source": {
                "type": "github_release",
                "repo": "example/test_module",
            },
            "workflows": [
                {
                    "name": "login_flow",
                    "entry_class": "legacy.LoginWorkflow",
                }
            ],
            "default_workflow": "login_flow",
            "data": _empty_data_contract(),
        }

        with pytest.raises(ValueError, match="entry_class"):
            ModuleManifest.from_dict(data)

    def test_from_dict_rejects_invalid_workflow_parameter(self):
        data = {
            "name": "test_module",
            "runtime_api": "core-native-v1",
            "version": "1.0.0",
            "upgrade_source": {
                "type": "github_release",
                "repo": "example/test_module",
            },
            "workflows": [
                {
                    "name": "login_flow",
                    "parameters": [
                        {"name": "bad_param", "type": "object"},
                    ],
                }
            ],
            "default_workflow": "login_flow",
            "data": _empty_data_contract(),
        }

        with pytest.raises(ValueError, match="parameters"):
            ModuleManifest.from_dict(data)

    def test_workflow_parameter_enum_options_allow_falsy_values(self):
        option_zero = WorkflowParameterOptionInfo.from_dict({"value": 0})
        option_false = WorkflowParameterOptionInfo.from_dict({"value": False})

        assert option_zero == WorkflowParameterOptionInfo(label="0", value=0)
        assert option_false == WorkflowParameterOptionInfo(label="False", value=False)


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
runtime_api: core-native-v2
version: 2.0.0
display_name: 测试模块
upgrade_source:
  type: github_release
  repo: example/test_module
"""
        (module_dir / "module.yaml").write_text(manifest_content)
        
        scanner = ModuleScanner(scan_paths=[tmp_path])
        
        manifest = scanner.parse_manifest(module_dir)
        
        assert manifest.name == "test_module"
        assert manifest.version == "2.0.0"
        assert manifest.runtime_api == "core-native-v2"

    def test_parse_manifest_rejects_duplicate_yaml_keys(self, tmp_path):
        from src.core.mms.models import ModuleParseError

        module_dir = tmp_path / "test_module"
        module_dir.mkdir()
        (module_dir / "module.yaml").write_text(
            "name: test_module\n"
            "runtime_api: core-native-v2\n"
            "name: shadow_module\n",
            encoding="utf-8",
        )

        scanner = ModuleScanner(scan_paths=[tmp_path])

        with pytest.raises(ModuleParseError, match="重复键: name"):
            scanner.parse_manifest(module_dir)

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
runtime_api: core-native-v2
upgrade_source:
  type: github_release
  repo: example/test_module
config_defaults:
  module:
    base_url: https://example.com
""".strip(),
            encoding="utf-8",
        )

        scanner = ModuleScanner(scan_paths=[tmp_path])
        manifest = scanner.parse_manifest(module_dir)

        assert manifest.config_defaults.module == {"base_url": "https://example.com"}
        assert manifest.config_defaults.workflows == {}

    def test_parse_manifest_rejects_unsupported_ui_extension_fields(self, tmp_path):
        from src.core.mms.models import ModuleParseError

        module_dir = tmp_path / "test_module"
        module_dir.mkdir()
        (module_dir / "module.yaml").write_text(
            """
name: test_module
runtime_api: core-native-v2
version: 1.0.0
upgrade_source:
  type: github_release
  repo: example/test_module
ui_extension:
  extra: unsupported
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
            runtime_api="core-native-v2",
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
            runtime_api="core-native-v2",
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
            runtime_api="core-native-v2",
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
            runtime_api="core-native-v2",
            version="1.0",
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
        _write_v2_runtime_package(module_dir)
        
        manifest_content = """
name: good_module
runtime_api: core-native-v2
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

    def test_validate_allows_additional_module_files(self, tmp_path):
        _write_v2_runtime_package(tmp_path)
        (tmp_path / "README.md").write_text("# demo_module\n", encoding="utf-8")
        manifest = ModuleManifest(
            name="demo_module",
            runtime_api="core-native-v2",
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
                "runtime_api": "core-native-v2",
                "upgrade_source": {
                    "type": "github_release",
                    "repo": "example/demo_module",
                },
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

        assert "config_defaults.workflows" in str(exc_info.value)

    def test_validate_rejects_duplicate_resource_pool_names(self, tmp_path):
        from src.core.mms.models import ModuleValidationError

        manifest = ModuleManifest.from_dict(
            {
                "name": "demo_module",
                "runtime_api": "core-native-v2",
                "upgrade_source": {
                    "type": "github_release",
                    "repo": "example/demo_module",
                },
                "resource_pools": [
                    {"name": "bound_account_ready"},
                    {"name": "bound_account_ready"},
                ],
            }
        )
        scanner = ModuleScanner(scan_paths=[tmp_path])

        with pytest.raises(ModuleValidationError) as exc_info:
            scanner.validate(manifest, tmp_path)

        assert "resource_pools" in str(exc_info.value)
