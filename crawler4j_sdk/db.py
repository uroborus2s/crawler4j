"""SDK 数据能力兼容层。

当前模块运行时真正拿到的数据接口，是 Core 注入到 ``TaskContext.db`` 上的
``DatabaseCapability``。

稳定支持的能力只有四类：

- 数据集查询：``list_records(dataset)``
- 数据集写入：``replace_records(dataset, records)``
- 轻量状态：``get_state`` / ``set_state`` / ``exists_state``
- 幂等锁：``acquire_lock`` / ``release_lock`` / ``is_locked``

历史上 SDK 曾保留一套 ``DataService`` 聚合抽象，但当前 Core 运行时并不会按那套
结构注入对象。为了避免现有模块项目里的导入语句直接失效，这里保留
``DataService`` 这个名字，并把它收口为当前真实运行时契约的兼容命名。

新模块代码请优先直接使用：

- ``from crawler4j_sdk import DatabaseCapability``
- 或直接在运行时代码中使用 ``ctx.db``
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from crawler4j_contracts import DatabaseCapability


@runtime_checkable
class DataService(DatabaseCapability, Protocol):
    """``TaskContext.db`` 的兼容命名。

    这是一个向后兼容的类型名，用来避免旧模块项目里
    ``from crawler4j_sdk import DataService`` 直接失效。

    当前真实可用的方法仍然完全以 ``DatabaseCapability`` 为准。
    """

    def list_records(self, dataset: str) -> list[dict[str, Any]]:
        ...

    def replace_records(self, dataset: str, records: list[dict[str, Any]]) -> bool:
        ...

    def acquire_lock(
        self,
        scope: str,
        key: str,
        *,
        ttl: int,
        owner: dict[str, Any] | None = None,
    ) -> bool:
        ...

    def release_lock(self, scope: str, key: str) -> bool:
        ...

    def is_locked(self, scope: str, key: str) -> bool:
        ...

    def get_state(self, key: str) -> Any:
        ...

    def set_state(self, key: str, value: Any, ttl: int | None = None) -> bool:
        ...

    def exists_state(self, key: str) -> bool:
        ...


__all__ = ["DataService", "DatabaseCapability"]
