"""ATM 运行配置模型。"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class EnvType(str, Enum):
    CHROME = "chrome"
    ANDROID = "android"
    BIT_BROWSER = "bit_browser"
    VIRTUAL_BROWSER = "virtual_browser"
    DEBUG_DUMMY = "debug_dummy"


class AcquisitionMode(str, Enum):
    SELECT = "select"
    CREATE = "create"


class CreationLifecycle(str, Enum):
    EPHEMERAL = "ephemeral"
    PERSISTENT = "persistent"


class CreationConfig(BaseModel):
    lifecycle: CreationLifecycle = Field(default=CreationLifecycle.PERSISTENT)
    params: Dict[str, Any] = Field(default_factory=dict)


class AcquisitionConfig(BaseModel):
    mode: AcquisitionMode = Field(default=AcquisitionMode.CREATE)
    provider: str = Field(default="virtualbrowser")
    env_type: EnvType = Field(default=EnvType.VIRTUAL_BROWSER)
    env_id: int | None = Field(default=None, ge=1)
    selector_name: str = Field(default="")
    resource_pool: str = Field(default="")
    wait_timeout: int = Field(default=60, ge=0)
    creation: CreationConfig = Field(default_factory=CreationConfig)

    @model_validator(mode="after")
    def _validate_mode_specific_fields(self) -> "AcquisitionConfig":
        if self.mode == AcquisitionMode.SELECT:
            has_env_id = self.env_id is not None
            has_selector = bool(self.selector_name.strip())
            has_resource_pool = bool(self.resource_pool.strip())
            if not has_env_id and not has_selector and not has_resource_pool:
                raise ValueError("selector_name or resource_pool or env_id is required when acquisition.mode=select")
        if self.mode == AcquisitionMode.CREATE and not self.provider.strip():
            raise ValueError("provider is required when acquisition.mode=create")
        return self


class ResourceConfig(BaseModel):
    acquisition: AcquisitionConfig = Field(default_factory=AcquisitionConfig)


class ExecutionContext(BaseModel):
    module: str
    workflow: str = "default"
    hooks_module: str = ""
    params: Dict[str, Any] = Field(default_factory=dict)
    object_bindings: Dict[str, str] = Field(default_factory=dict)
    object_params: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    timeout: int = Field(default=600, ge=0)


class RunProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resource: ResourceConfig = Field(default_factory=ResourceConfig)
    execution: Optional[ExecutionContext] = None

    def to_yaml(self) -> str:
        return yaml.dump(self.model_dump(mode="json"), allow_unicode=True, sort_keys=False)

    @classmethod
    def from_yaml(cls, yaml_content: str) -> "RunProfile":
        data = yaml.safe_load(yaml_content)
        return cls(**data)
