"""IP 池管理模块。

设计参考: docs/03-solution/reference-design/module-01-runtime-environment.md §5.2

提供 IP 池的管理功能：
    - IPEntry: IP 条目数据类
    - IPPool: IP 池
    - IPPoolManager: IP 池管理器
    - IPStrategy: IP 分配策略
"""

import json
import math
import secrets
import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from src.core.foundation.logging import logger
from src.core.persistence.database import STATE_DB, get_connection

MANUAL_LOCATION_RANDOM_RADIUS_M = 1000
EARTH_RADIUS_M = 6_371_008.8


class IPStrategy(StrEnum):
    """IP 分配策略。

    设计文档 5.2.3: IP 分配策略
    """

    LEAST_RECENTLY_USED = "least_recently_used"  # 最久未使用（LRU）
    LEAST_BOUND = "least_bound"  # 最少绑定数量（负载均衡）
    HIGHEST_SAFETY = "highest_safety"  # 最高安全度评分
    LONGEST_TTL = "longest_ttl"  # 最长有效期
    SYSTEM_PROXY = "system_proxy"  # 使用系统代理
    NONE = "none"  # 不使用代理


class IPEntryStatus(StrEnum):
    """IP 条目人工状态。"""

    AVAILABLE = "available"  # 可用于后续绑定
    DISABLED = "disabled"  # 停用，仅保留已有绑定，不再参与后续绑定


def _normalize_entry_status(status: IPEntryStatus | str | None) -> IPEntryStatus:
    if isinstance(status, IPEntryStatus):
        return status
    try:
        return IPEntryStatus(status or IPEntryStatus.AVAILABLE.value)
    except ValueError:
        logger.warning(f"[IPPool] 未知 IP 条目状态，回退为可用: {status}")
        return IPEntryStatus.AVAILABLE


def _safe_coordinate(value: Any, *, lower: float, upper: float) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if lower <= number <= upper else None


def _random_unit() -> float:
    return secrets.randbelow(1_000_000) / 1_000_000


def _random_geo_near(
    latitude: float, longitude: float, *, radius_m: int = MANUAL_LOCATION_RANDOM_RADIUS_M
) -> tuple[float, float]:
    distance = radius_m * math.sqrt(_random_unit())
    bearing = 2 * math.pi * _random_unit()
    lat1 = math.radians(latitude)
    lon1 = math.radians(longitude)
    angular_distance = distance / EARTH_RADIUS_M

    lat2 = math.asin(
        math.sin(lat1) * math.cos(angular_distance) + math.cos(lat1) * math.sin(angular_distance) * math.cos(bearing)
    )
    lon2 = lon1 + math.atan2(
        math.sin(bearing) * math.sin(angular_distance) * math.cos(lat1),
        math.cos(angular_distance) - math.sin(lat1) * math.sin(lat2),
    )
    normalized_lon = (math.degrees(lon2) + 540) % 360 - 180
    return math.degrees(lat2), normalized_lon


@dataclass
class IPEntry:
    """IP 条目。

    Attributes:
        id: 条目唯一 ID
        pool_id: 所属 IP 池 ID
        address: IP 地址
        protocol: 协议 (http/socks5)
        port: 端口
        username: 认证用户名
        password: 认证密码
        bound_count: 绑定的环境数量
        safety_score: 安全度评分 (0-100)
        expires_at: 过期时间戳
        created_at: 创建时间戳
        updated_at: 更新时间戳
        last_used_at: 最近使用时间戳
        status: 人工状态，可用或不可用
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    pool_id: str = ""
    address: str = ""
    protocol: str = "http"
    port: int = 0
    username: str | None = None
    password: str | None = None
    bound_count: int = 0
    safety_score: int = 100
    expires_at: int | None = None
    created_at: int = field(default_factory=lambda: int(time.time()))
    updated_at: int = field(default_factory=lambda: int(time.time()))
    last_used_at: int | None = None
    status: IPEntryStatus = IPEntryStatus.AVAILABLE
    manual_latitude: float | None = None
    manual_longitude: float | None = None

    def to_proxy_string(self) -> str:
        """转换为代理字符串格式。"""
        auth = ""
        if self.username and self.password:
            auth = f"{self.username}:{self.password}@"
        return f"{self.protocol}://{auth}{self.address}:{self.port}"

    def is_expired(self) -> bool:
        """检查是否已过期。"""
        if self.expires_at is None:
            return False
        return int(time.time()) > self.expires_at

    def is_available(self) -> bool:
        """检查是否允许参与后续绑定。"""
        return _normalize_entry_status(self.status) == IPEntryStatus.AVAILABLE

    def random_manual_geo(self) -> dict[str, float] | None:
        """按手动经纬度随机生成 1 公里内的创建位置。"""
        latitude = _safe_coordinate(self.manual_latitude, lower=-90, upper=90)
        longitude = _safe_coordinate(self.manual_longitude, lower=-180, upper=180)
        if latitude is None or longitude is None:
            return None
        randomized_latitude, randomized_longitude = _random_geo_near(latitude, longitude)
        return {
            "latitude": randomized_latitude,
            "longitude": randomized_longitude,
        }

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典。"""
        return {
            "id": self.id,
            "pool_id": self.pool_id,
            "address": self.address,
            "protocol": self.protocol,
            "port": self.port,
            "username": self.username,
            "password": self.password,
            "bound_count": self.bound_count,
            "safety_score": self.safety_score,
            "expires_at": self.expires_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_used_at": self.last_used_at,
            "status": _normalize_entry_status(self.status).value,
            "manual_latitude": self.manual_latitude,
            "manual_longitude": self.manual_longitude,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IPEntry":
        """从字典反序列化。"""
        return cls(
            id=data["id"],
            pool_id=data.get("pool_id", ""),
            address=data.get("address", ""),
            protocol=data.get("protocol", "http"),
            port=data.get("port", 0),
            username=data.get("username"),
            password=data.get("password"),
            bound_count=data.get("bound_count", 0),
            safety_score=data.get("safety_score", 100),
            expires_at=data.get("expires_at"),
            created_at=data.get("created_at", int(time.time())),
            updated_at=data.get("updated_at", data.get("created_at", int(time.time()))),
            last_used_at=data.get("last_used_at"),
            status=_normalize_entry_status(data.get("status")),
            manual_latitude=_safe_coordinate(data.get("manual_latitude"), lower=-90, upper=90),
            manual_longitude=_safe_coordinate(data.get("manual_longitude"), lower=-180, upper=180),
        )


@dataclass
class IPPool:
    """IP 池。

    Attributes:
        id: 池唯一 ID
        name: 池名称
        provider: 提供商 (local/api)
        strategy: 分配策略
        entries: IP 条目列表
        config: 额外配置
        created_at: 创建时间戳
        updated_at: 更新时间戳
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    provider: str = "local"
    strategy: IPStrategy = IPStrategy.LEAST_RECENTLY_USED
    entries: list[IPEntry] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)
    created_at: int = field(default_factory=lambda: int(time.time()))
    updated_at: int = field(default_factory=lambda: int(time.time()))

    def select_ip(
        self,
        exclude_ids: set[str] | None = None,
        strategy: IPStrategy | str | None = None,
    ) -> IPEntry | None:
        """根据策略选择 IP。

        Args:
            exclude_ids: 排除的 IP ID 集合

        Returns:
            选中的 IP 条目，若无可用则返回 None
        """
        exclude = exclude_ids or set()
        candidates = [ip for ip in self.entries if ip.id not in exclude and ip.is_available() and not ip.is_expired()]

        if not candidates:
            return None

        selected_strategy = self.strategy
        if strategy:
            try:
                selected_strategy = IPStrategy(strategy)
            except ValueError:
                logger.warning(f"[IPPool] 未知的 IP 绑定策略，回退到池默认策略: {strategy}")

        match selected_strategy:
            case IPStrategy.LEAST_RECENTLY_USED:
                return min(
                    candidates,
                    key=lambda ip: (
                        ip.last_used_at is not None,
                        ip.last_used_at or 0,
                        ip.bound_count,
                        ip.created_at,
                        ip.id,
                    ),
                )

            case IPStrategy.LEAST_BOUND:
                return min(candidates, key=lambda ip: ip.bound_count)

            case IPStrategy.HIGHEST_SAFETY:
                return max(candidates, key=lambda ip: ip.safety_score)

            case IPStrategy.LONGEST_TTL:
                valid = [ip for ip in candidates if ip.expires_at]
                if not valid:
                    return candidates[0] if candidates else None
                return max(valid, key=lambda ip: ip.expires_at or 0)

            case IPStrategy.SYSTEM_PROXY:
                # 返回特殊标记
                return IPEntry(id="system", address="system://proxy")

            case IPStrategy.NONE:
                return None

            case _:
                return candidates[0] if candidates else None

    def add_entry(self, entry: IPEntry) -> None:
        """添加 IP 条目。"""
        entry.pool_id = self.id
        self.entries.append(entry)
        self.updated_at = int(time.time())

    def remove_entry(self, entry_id: str) -> bool:
        """移除 IP 条目。"""
        for i, entry in enumerate(self.entries):
            if entry.id == entry_id:
                self.entries.pop(i)
                self.updated_at = int(time.time())
                return True
        return False

    def get_entry(self, entry_id: str) -> IPEntry | None:
        """获取 IP 条目。"""
        for entry in self.entries:
            if entry.id == entry_id:
                return entry
        return None


class IPPoolManager:
    """IP 池管理器。

    设计文档 5.2.2: IPPoolManager
    """

    def __init__(self) -> None:
        """初始化 IP 池管理器。"""
        self._pools: dict[str, IPPool] = {}
        self._env_bindings: dict[int, str] = {}  # 当前进程内 env_id -> ip_id

    async def startup(self) -> None:
        """启动管理器，从数据库加载数据。"""
        await self._load_from_db()

        # 如果没有 IP 池，创建默认池
        if not self._pools:
            self._create_default_pool()

        logger.info(f"[IPPool] 已加载 {len(self._pools)} 个 IP 池")

    def _create_default_pool(self) -> None:
        """创建默认 IP 池。"""
        default_pool = IPPool(
            name="默认池",
            provider="local",
            strategy=IPStrategy.LEAST_RECENTLY_USED,
        )
        self.add_pool(default_pool)
        logger.info("[IPPool] 已创建默认 IP 池")

    def add_pool(self, pool: IPPool) -> None:
        """添加 IP 池。"""
        self._pools[pool.id] = pool
        self._persist_pool(pool)

    def remove_pool(self, pool_id: str) -> bool:
        """移除 IP 池。"""
        if pool_id in self._pools:
            del self._pools[pool_id]
            self._delete_pool(pool_id)
            return True
        return False

    def get_pool(self, pool_id: str) -> IPPool | None:
        """获取 IP 池。"""
        return self._pools.get(pool_id)

    def list_pools(self) -> list[IPPool]:
        """列出所有 IP 池。"""
        return list(self._pools.values())

    def get_entry(self, entry_id: str) -> IPEntry | None:
        """按条目 ID 获取 IP。"""
        normalized_entry_id = str(entry_id or "").strip()
        if not normalized_entry_id:
            return None
        for pool in self._pools.values():
            entry = pool.get_entry(normalized_entry_id)
            if entry is not None:
                return entry
        return None

    async def bind_ip_entry(
        self,
        env_id: int,
        entry_id: str,
        *,
        old_entry_id: str | None = None,
    ) -> IPEntry | None:
        """为环境绑定指定 IP 条目。"""
        try:
            eid = int(env_id)
        except (ValueError, TypeError):
            return None

        entry = self.get_entry(entry_id)
        if entry is None or not entry.is_available() or entry.is_expired():
            logger.warning(f"[IPPool] 指定 IP 不可用: entry={entry_id}")
            return None

        current_id = self._env_bindings.get(eid) or str(old_entry_id or "").strip()
        if current_id == entry.id:
            self._env_bindings[eid] = entry.id
            return entry

        old_entry = self.get_entry(current_id)
        if old_entry is not None:
            old_entry.bound_count = max(0, old_entry.bound_count - 1)
            self._persist_entry(old_entry)

        now = int(time.time())
        entry.bound_count += 1
        entry.last_used_at = now
        entry.updated_at = now
        self._env_bindings[eid] = entry.id
        self._persist_entry(entry)
        logger.info(f"[IPPool] 绑定指定 IP 成功: env={env_id} ip={entry.address} (new_count={entry.bound_count})")
        return entry

    async def bind_ip(
        self,
        env_id: int,
        pool_id: str,
        strategy: str | IPStrategy | None = None,
    ) -> IPEntry | None:
        """为环境绑定 IP。

        Args:
            env_id: 环境 ID
            pool_id: IP 池 ID

        Returns:
            绑定的 IP 条目，若无可用则返回 None
        """
        pool = self._pools.get(pool_id)
        if not pool:
            logger.warning(f"[IPPool] 池不存在: {pool_id}")
            return None

        # 选择 IP
        ip = pool.select_ip(strategy=strategy)
        if not ip:
            logger.warning(f"[IPPool] 无可用 IP: pool={pool_id}")
            return None

        # 只有选到新 IP 后才替换旧绑定；停用只影响后续候选，不自动解绑已有环境。
        await self.unbind_ip(env_id)

        now = int(time.time())
        ip.bound_count += 1
        ip.last_used_at = now
        ip.updated_at = now
        self._env_bindings[int(env_id)] = ip.id
        self._persist_entry(ip)

        logger.info(f"[IPPool] 绑定 IP成功: env={env_id} ip={ip.address} (new_count={ip.bound_count})")
        return ip

    def mark_entry_used(self, entry_id: str) -> bool:
        """刷新 IP 条目的最近使用时间。"""
        normalized_entry_id = str(entry_id or "").strip()
        if not normalized_entry_id:
            return False

        now = int(time.time())
        for pool in self._pools.values():
            entry = pool.get_entry(normalized_entry_id)
            if entry is None:
                continue
            entry.last_used_at = now
            entry.updated_at = now
            self._persist_entry(entry)
            logger.info(f"[IPPool] IP 使用时间已刷新: id={normalized_entry_id}")
            return True
        logger.warning(f"[IPPool] 刷新 IP 使用时间时未找到条目: id={normalized_entry_id}")
        return False

    def set_entry_status(self, entry_id: str, status: IPEntryStatus | str) -> bool:
        """设置 IP 条目的人工状态，不影响已有环境绑定。"""
        next_status = _normalize_entry_status(status)
        for pool in self._pools.values():
            entry = pool.get_entry(entry_id)
            if entry is None:
                continue
            entry.status = next_status
            entry.updated_at = int(time.time())
            self._persist_entry(entry)
            logger.info(f"[IPPool] IP 状态已更新: id={entry_id} status={next_status.value}")
            return True
        logger.warning(f"[IPPool] 更新 IP 状态时未找到条目: id={entry_id}")
        return False

    async def unbind_ip(self, env_id: int) -> bool:
        """解绑环境的 IP。

        Args:
            env_id: 环境 ID

        Returns:
            是否解绑成功
        """
        try:
            eid = int(env_id)
        except (ValueError, TypeError):
            return False

        ip_id = self._env_bindings.pop(eid, None)

        if not ip_id:
            return False

        # 查找并更新 IP
        found = False
        for pool in self._pools.values():
            ip = pool.get_entry(ip_id)
            if ip:
                ip.bound_count = max(0, ip.bound_count - 1)
                self._persist_entry(ip)
                found = True
                logger.info(f"[IPPool] 解绑 IP 成功: env={env_id} ip={ip.address} (new_count={ip.bound_count})")
                break

        if not found:
            logger.warning(f"[IPPool] 解绑 IP 时未找到对应的 IP 条目: id={ip_id}")

        return True

    def get_bound_ip(self, env_id: int) -> IPEntry | None:
        """获取环境绑定的 IP。"""
        ip_id = self._env_bindings.get(env_id)
        if not ip_id:
            return None

        for pool in self._pools.values():
            ip = pool.get_entry(ip_id)
            if ip:
                return ip
        return None

    # ========== 数据库操作 ==========

    def _persist_pool(self, pool: IPPool) -> None:
        """持久化 IP 池。"""
        with get_connection(STATE_DB) as conn:
            conn.execute(
                """
                INSERT INTO ip_pools (id, name, provider, strategy, config_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    strategy = excluded.strategy,
                    config_json = excluded.config_json,
                    updated_at = excluded.updated_at
                """,
                (
                    pool.id,
                    pool.name,
                    pool.provider,
                    pool.strategy.value,
                    json.dumps(pool.config),
                    pool.created_at,
                    pool.updated_at,
                ),
            )

    def _delete_pool(self, pool_id: str) -> None:
        """删除 IP 池。"""
        with get_connection(STATE_DB) as conn:
            conn.execute("DELETE FROM ip_pools WHERE id = ?", (pool_id,))

    def _persist_entry(self, entry: IPEntry) -> None:
        """持久化 IP 条目。"""
        entry.updated_at = int(time.time())
        with get_connection(STATE_DB) as conn:
            conn.execute(
                """
                INSERT INTO ip_entries (
                    id, pool_id, address, protocol, port, username, password,
                    bound_count, safety_score, expires_at, created_at, updated_at, last_used_at, status,
                    manual_latitude, manual_longitude
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    pool_id = excluded.pool_id,
                    address = excluded.address,
                    protocol = excluded.protocol,
                    port = excluded.port,
                    username = excluded.username,
                    password = excluded.password,
                    bound_count = excluded.bound_count,
                    safety_score = excluded.safety_score,
                    expires_at = excluded.expires_at,
                    updated_at = excluded.updated_at,
                    last_used_at = excluded.last_used_at,
                    status = excluded.status,
                    manual_latitude = excluded.manual_latitude,
                    manual_longitude = excluded.manual_longitude
                """,
                (
                    entry.id,
                    entry.pool_id,
                    entry.address,
                    entry.protocol,
                    entry.port,
                    entry.username,
                    entry.password,
                    entry.bound_count,
                    entry.safety_score,
                    entry.expires_at,
                    entry.created_at,
                    entry.updated_at,
                    entry.last_used_at,
                    _normalize_entry_status(entry.status).value,
                    entry.manual_latitude,
                    entry.manual_longitude,
                ),
            )

    async def _load_from_db(self) -> None:
        """从数据库加载数据。"""
        with get_connection(STATE_DB) as conn:
            # 加载池
            cursor = conn.execute("SELECT * FROM ip_pools")
            for row in cursor.fetchall():
                pool = IPPool(
                    id=row["id"],
                    name=row["name"],
                    provider=row["provider"],
                    strategy=IPStrategy(row["strategy"]) if row["strategy"] else IPStrategy.LEAST_BOUND,
                    config=json.loads(row["config_json"]) if row["config_json"] else {},
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
                self._pools[pool.id] = pool

            # 加载条目
            cursor = conn.execute("SELECT * FROM ip_entries")
            for row in cursor.fetchall():
                entry = IPEntry(
                    id=row["id"],
                    pool_id=row["pool_id"],
                    address=row["address"],
                    protocol=row["protocol"],
                    port=row["port"],
                    username=row["username"],
                    password=row["password"],
                    bound_count=row["bound_count"] if row["bound_count"] is not None else 0,
                    safety_score=row["safety_score"] if row["safety_score"] is not None else 100,
                    expires_at=row["expires_at"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    last_used_at=row["last_used_at"],
                    status=_normalize_entry_status(row["status"]),
                    manual_latitude=_safe_coordinate(row["manual_latitude"], lower=-90, upper=90),
                    manual_longitude=_safe_coordinate(row["manual_longitude"], lower=-180, upper=180),
                )
                pool = self._pools.get(entry.pool_id)
                if pool:
                    pool.entries.append(entry)


# 全局单例
_ip_pool_manager: IPPoolManager | None = None


def get_ip_pool_manager() -> IPPoolManager:
    """获取全局 IPPoolManager 实例。"""
    global _ip_pool_manager
    if _ip_pool_manager is None:
        _ip_pool_manager = IPPoolManager()
    return _ip_pool_manager
