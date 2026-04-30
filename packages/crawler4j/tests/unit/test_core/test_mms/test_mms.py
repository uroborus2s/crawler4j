"""MMS 数据模型单元测试。"""

import time

import pytest

from crawler4j_contracts import Crawler4jMeta, TaskContext, TaskResult

from src.core.mms.models import (
    ConfigDefaultsInfo,
    ModuleManifest,
    ModuleSource,
    ModuleStatus,
    UpgradeSourceInfo,
)
from src.core.mms.scanner import ModuleScanner
from src.core.mms.service import ModuleService
from src.core.mms.runtime_descriptor import ModuleRuntimeDescriptorV2, V2RuntimeEntry


def _empty_data_contract() -> dict[str, list[dict[str, object]]]:
    return {"resources": [], "views": [], "queries": [], "seeds": []}


def _write_v2_runtime_package(module_dir) -> None:
    module_dir.mkdir(parents=True, exist_ok=True)
    (module_dir / "__init__.py").write_text("", encoding="utf-8")
    for package_name in ("interfaces", "objects", "workflows", "tasks", "data", "pages", "candidates"):
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
            "runtime_api": "core-native-v2",
            "version": "1.0.0",
            "display_name": "测试模块",
            "upgrade_source": {
                "type": "github_release",
                "repo": "example/test_module",
            },
            "config_defaults": {
                "module": {
                    "base_url": "https://example.com",
                },
            },
        }

        manifest = ModuleManifest.from_dict(data)

        assert manifest.name == "test_module"
        assert manifest.version == "1.0.0"
        assert manifest.runtime_api == "core-native-v2"
        assert manifest.upgrade_source.repo == "example/test_module"
        assert manifest.config_defaults.module == {"base_url": "https://example.com"}
        assert manifest.config_defaults.workflows == {}
        assert manifest.data == _empty_data_contract()
        assert not hasattr(manifest, "workflows")
        assert not hasattr(manifest, "default_workflow")
    
    def test_to_dict(self):
        """测试序列化。"""
        manifest = ModuleManifest(
            name="test_module",
            runtime_api="core-native-v2",
            upgrade_source=UpgradeSourceInfo(repo="example/test_module"),
            config_defaults=ConfigDefaultsInfo(
                module={"base_url": "https://example.com"},
            ),
            data=_empty_data_contract(),
        )
        
        data = manifest.to_dict()

        assert data["name"] == "test_module"
        assert data["runtime_api"] == "core-native-v2"
        assert data["upgrade_source"] == {
            "type": "github_release",
            "repo": "example/test_module",
            "allow_prerelease": False,
        }
        assert "ui_extension" not in data
        assert data["config_defaults"] == {
            "module": {"base_url": "https://example.com"},
            "workflows": {},
        }
        assert "resource_pools" not in data
        assert "workflows" not in data
        assert "default_workflow" not in data
        assert "data" not in data

    def test_from_dict_rejects_removed_resource_pools(self):
        with pytest.raises(ValueError, match="resource_pools"):
            ModuleManifest.from_dict(
                {
                    "name": "test_module",
                    "runtime_api": "core-native-v2",
                    "upgrade_source": {
                        "type": "github_release",
                        "repo": "example/test_module",
                    },
                    "resource_pools": [
                        {"name": "bound_account_ready"},
                    ],
                }
            )

    def test_from_dict_rejects_removed_workflows(self):
        """workflows 不再是 module.yaml 的兼容面。"""
        data = {
            "name": "test_module",
            "runtime_api": "core-native-v2",
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
        }

        with pytest.raises(ValueError, match="workflows"):
            ModuleManifest.from_dict(data)

    def test_from_dict_rejects_removed_data_contract_cache(self):
        data = {
            "name": "test_module",
            "runtime_api": "core-native-v2",
            "version": "1.0.0",
            "upgrade_source": {
                "type": "github_release",
                "repo": "example/test_module",
            },
            "data": _empty_data_contract(),
        }

        with pytest.raises(ValueError, match="data"):
            ModuleManifest.from_dict(data)


def test_env_candidates_invoke_uses_keyword_binding_for_params_after_optional_defaults():
    def ready(limit: int = 100, params: dict | None = None):
        return [int(params["env_id"]), limit]

    result = ModuleService._invoke_env_candidates(
        ready,
        TaskContext(env_id=0, task_name="demo_module"),
        {"env_id": 42},
    )

    assert result == [42, 100]


def test_env_cleanup_candidates_invoke_uses_same_keyword_binding():
    def cleanup(limit: int = 100, params: dict | None = None):
        return [int(params["env_id"]), limit]

    result = ModuleService._invoke_env_id_provider(
        cleanup,
        TaskContext(env_id=0, task_name="demo_module"),
        {"env_id": 43},
        label="env_cleanup_candidates",
    )

    assert result == [43, 100]


@pytest.mark.asyncio
async def test_resolve_env_candidates_async_times_out_without_blocking_loop():
    service = ModuleService()

    def slow_resolve(*_args, **_kwargs):
        time.sleep(0.2)
        return [1]

    service.resolve_env_candidates = slow_resolve  # type: ignore[method-assign]

    with pytest.raises(TimeoutError, match="env_candidates 执行超时"):
        await service.resolve_env_candidates_async(
            "demo_module",
            TaskContext(env_id=0, task_name="demo_module"),
            "slow_accounts",
            timeout=0.01,
        )


@pytest.mark.asyncio
async def test_resolve_env_cleanup_candidates_async_times_out_without_blocking_loop():
    service = ModuleService()

    def slow_resolve(*_args, **_kwargs):
        time.sleep(0.2)
        return [1]

    service.resolve_env_cleanup_candidates = slow_resolve  # type: ignore[method-assign]

    with pytest.raises(TimeoutError, match="env_cleanup_candidates 执行超时"):
        await service.resolve_env_cleanup_candidates_async(
            "demo_module",
            TaskContext(env_id=0, task_name="demo_module"),
            "unused_accounts",
            timeout=0.01,
        )


@pytest.mark.asyncio
async def test_run_v2_workflow_runs_object_cleanup_after_workflow_run(monkeypatch):
    cleanup_outcome = None

    class Workflow:
        def run(self, ctx: TaskContext):
            return TaskResult.ok(message="ok")

    class FakeContainer:
        def __init__(self, *_args, **_kwargs):
            pass

        def build_workflow(self):
            return Workflow()

        async def cleanup(self, _context, outcome, *, timeout_seconds=None):
            nonlocal cleanup_outcome
            cleanup_outcome = outcome

    monkeypatch.setattr("src.core.mms.service.ObjectContainerV2", FakeContainer)
    descriptor = ModuleRuntimeDescriptorV2(
        workflows={
            "default": V2RuntimeEntry(
                meta=Crawler4jMeta(kind="workflow", name="default"),
                target=Workflow,
                module_name="demo_module.workflows.default",
                attr_name="Workflow",
                owner="workflows/default.py",
            )
        }
    )

    result = await ModuleService()._run_v2_workflow(
        descriptor,
        TaskContext(env_id=1, task_name="demo_module", runtime={"workflow": "default"}),
    )

    assert result.success is True
    assert cleanup_outcome is not None
    assert cleanup_outcome.status == "succeeded"


@pytest.mark.asyncio
async def test_run_v2_workflow_runs_object_cleanup_after_workflow_error(monkeypatch):
    cleanup_outcome = None

    class Workflow:
        def run(self, ctx: TaskContext):
            raise RuntimeError("boom")

    class FakeContainer:
        def __init__(self, *_args, **_kwargs):
            pass

        def build_workflow(self):
            return Workflow()

        async def cleanup(self, _context, outcome, *, timeout_seconds=None):
            nonlocal cleanup_outcome
            cleanup_outcome = outcome

    monkeypatch.setattr("src.core.mms.service.ObjectContainerV2", FakeContainer)
    descriptor = ModuleRuntimeDescriptorV2(
        workflows={
            "default": V2RuntimeEntry(
                meta=Crawler4jMeta(kind="workflow", name="default"),
                target=Workflow,
                module_name="demo_module.workflows.default",
                attr_name="Workflow",
                owner="workflows/default.py",
            )
        }
    )

    with pytest.raises(RuntimeError, match="boom"):
        await ModuleService()._run_v2_workflow(
            descriptor,
            TaskContext(env_id=1, task_name="demo_module", runtime={"workflow": "default"}),
        )

    assert cleanup_outcome is not None
    assert cleanup_outcome.status == "failed"
    assert cleanup_outcome.error_type == "RuntimeError"


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

    def test_parse_manifest_rejects_removed_ui_extension_pages(self, tmp_path):
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
  pages:
    - id: custom_page
      label: 自定义页面
""".strip(),
            encoding="utf-8",
        )

        scanner = ModuleScanner(scan_paths=[tmp_path])

        with pytest.raises(ModuleParseError) as exc_info:
            scanner.parse_manifest(module_dir)

        assert "ui_extension" in str(exc_info.value)

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
