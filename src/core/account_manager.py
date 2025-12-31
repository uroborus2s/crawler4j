"""Account manager module.

Handles scheduling logic for Ctrip and Labor account pools.
"""

from src.core.models.ctrip_account import CtripAccount
from src.core.models.environment import Environment, EnvironmentStatus
from src.core.models.labor_account import LaborAccount
from src.utils.logger import logger
from src.utils.storage import (
    CtripAccountRepository,
    EnvironmentRepository,
    LaborAccountRepository,
    ProxyIPRepository,
)


class AccountManager:
    """Manages account pools and environment scheduling.

    Scheduling Logic:
    1. Select an active Ctrip account
    2. Check if it has an existing environment
    3. If yes: start the environment
    4. If no: find an unbound active Labor account, create new environment
    5. If Ctrip account is banned: delete environment, blacklist account
    """

    def __init__(self):
        self.ctrip_repo = CtripAccountRepository()
        self.labor_repo = LaborAccountRepository()
        self.env_repo = EnvironmentRepository()
        self.proxy_repo = ProxyIPRepository()

    # ==================== 调度器方法 ====================

    def get_idle_environment(self) -> Environment | None:
        """获取一个空闲且有效的环境，使用智能选择策略。

        筛选条件：
        1. 环境状态为空闲
        2. 关联的携程账号状态为 active
        3. 今日打开次数未达到限制 (daily_open_limit == 0 或 daily_open_count < daily_open_limit)

        优先级排序：
        - 优先选择 daily_open_count 最小的环境（使用次数最少）
        - 如果 last_open_date 不是今天，daily_open_count 视为 0

        Returns:
            Environment if found, None otherwise.
        """
        from datetime import date

        idle_envs = self.env_repo.get_idle()

        # 筛选符合条件的环境
        valid_envs: list[Environment] = []
        today = date.today()

        for env_data in idle_envs:
            # 1. 验证关联的携程账号是否有效
            ctrip_id = env_data.get("ctrip_account_id")
            if not ctrip_id:
                continue

            ctrip_data = self.ctrip_repo.get_by_id(ctrip_id)
            if not ctrip_data or ctrip_data.get("status") != "active":
                continue

            # 2. 转换为 Environment 对象
            env = Environment.from_dict(env_data)

            # 3. 检查今日打开次数限制
            if not env.can_open_today():
                logger.debug(
                    f"环境 {env.id} 今日打开次数已达上限 ({env.daily_open_count}/{env.daily_open_limit})"
                )
                continue

            valid_envs.append(env)

        if not valid_envs:
            return None

        # 4. 按优先级排序：今日使用次数最少的优先
        def get_effective_count(env: Environment) -> int:
            """获取有效的今日使用次数。如果 last_open_date 不是今天，返回 0。"""
            if env.last_open_date != today:
                return 0
            return env.daily_open_count

        # 排序：使用次数升序
        valid_envs.sort(key=get_effective_count)

        selected = valid_envs[0]
        logger.info(
            f"智能选择环境: ENV-{selected.id} (今日使用: {get_effective_count(selected)}次)"
        )

        return selected

    def create_environment_auto(self) -> Environment | None:
        """自动创建新环境（同步版本，不支持接码平台）。

        Returns:
            New Environment if successful, None otherwise.
        """
        from src.core.environment_manager import EnvironmentManager

        manager = EnvironmentManager()
        return manager.create_environment(auto_assign=True)

    async def create_environment_auto_async(self) -> Environment | None:
        """自动创建新环境（异步版本，支持接码平台）。

        调度器应使用此方法。

        Returns:
            New Environment if successful, None otherwise.
        """
        from src.core.environment_manager import EnvironmentManager

        manager = EnvironmentManager()
        return await manager.create_environment_async(auto_assign=True)

    def cleanup_environment(self, env_id: int) -> bool:
        """清理环境连接信息，释放劳保账号锁定，将状态设为 idle。

        Args:
            env_id: Environment ID.

        Returns:
            True if successful.
        """
        try:
            # 1. 释放该环境锁定的所有劳保账号
            released = self.labor_repo.force_unlock_by_env(env_id)
            if released > 0:
                logger.info(f"🔓 ENV-{env_id} 释放了 {released} 个劳保账号锁定")

            # 2. 清理连接信息
            self.env_repo.update_connection_info(env_id, None, None, None)

            # 3. 更新状态
            return self.env_repo.update_status(env_id, "idle")
        except Exception as e:
            logger.error(f"清理环境失败: {e}")
            return False

    def handle_blacklisted_account(self, ctrip_account_id: int) -> bool:
        """处理被封的携程账号。

        委托给 EnvironmentManager 执行统一销毁流程。

        Args:
            ctrip_account_id: Ctrip account ID.

        Returns:
            True if successful.
        """
        from src.core.environment_manager import DestroyReason, EnvironmentManager

        manager = EnvironmentManager()
        return manager.destroy_by_ctrip_account(
            ctrip_account_id, DestroyReason.BLACKLISTED
        )

    # ==================== 原有方法 ====================

    def get_next_environment(self) -> Environment | None:
        """Get the next available environment for task execution.

        Returns:
            Environment if one is available, None otherwise.
        """
        # Get active Ctrip accounts
        ctrip_accounts = self.ctrip_repo.get_active()

        for ctrip_data in ctrip_accounts:
            ctrip = CtripAccount.from_dict(ctrip_data)

            # Check if this account has an existing environment
            env_data = self.env_repo.get_by_ctrip_account(ctrip.id)

            if env_data:
                env = Environment.from_dict(env_data)
                if env.is_idle:
                    return env
            else:
                # No environment - try to create one
                env = self._create_environment_for_ctrip(ctrip)
                if env:
                    return env

        return None

    def _create_environment_for_ctrip(self, ctrip: CtripAccount) -> Environment | None:
        """Create a new environment for a Ctrip account.

        Args:
            ctrip: The Ctrip account to create environment for.

        Returns:
            New Environment if successful, None otherwise.
        """
        # Find an unbound active Labor account
        labor_accounts = self.labor_repo.get_active_unbound()

        if not labor_accounts:
            return None

        labor_data = labor_accounts[0]
        labor = LaborAccount.from_dict(labor_data)

        # Generate browser profile ID (will be created by browser API)
        browser_profile_id = f"profile_{ctrip.id}_{labor.id}"

        # Create environment
        env_id = self.env_repo.create(
            ctrip_account_id=ctrip.id,
            labor_account_id=labor.id,
            browser_profile_id=browser_profile_id,
        )

        return Environment(
            id=env_id,
            ctrip_account_id=ctrip.id,
            labor_account_id=labor.id,
            browser_profile_id=browser_profile_id,
            status=EnvironmentStatus.IDLE,
        )

    def start_environment(self, env_id: int) -> bool:
        """Mark environment as running.

        Args:
            env_id: Environment ID.

        Returns:
            True if successful.
        """
        return self.env_repo.update_status(env_id, "running")

    def stop_environment(self, env_id: int) -> bool:
        """Mark environment as idle.

        Args:
            env_id: Environment ID.

        Returns:
            True if successful.
        """
        return self.env_repo.update_status(env_id, "idle")

    def blacklist_ctrip_account(self, ctrip_account_id: int) -> bool:
        """Blacklist a Ctrip account and delete its environment.

        Called when account is banned or logged out.

        Args:
            ctrip_account_id: Ctrip account ID.

        Returns:
            True if successful.
        """
        # Delete environment first
        env_data = self.env_repo.get_by_ctrip_account(ctrip_account_id)
        if env_data:
            self.env_repo.delete(env_data["id"])

        # Blacklist the account
        return self.ctrip_repo.update_status(ctrip_account_id, "blacklisted")

    def update_labor_stats(
        self,
        labor_account_id: int,
        completed: int = 0,
        discarded: int = 0,
        approved: int = 0,
        rejected: int = 0,
    ) -> bool:
        """Update statistics for a Labor account.

        Args:
            labor_account_id: Labor account ID.
            completed: Number of completed tasks to add.
            discarded: Number of discarded tasks to add.
            approved: Number of approved tasks to add.
            rejected: Number of rejected tasks to add.

        Returns:
            True if successful.
        """
        return self.labor_repo.update_stats(
            labor_account_id,
            completed=completed,
            discarded=discarded,
            approved=approved,
            rejected=rejected,
        )

    def get_running_count(self) -> int:
        """Get count of currently running environments."""
        return self.env_repo.get_running_count()

    def get_active_ctrip_count(self) -> int:
        """Get count of active Ctrip accounts."""
        return self.ctrip_repo.count("status = 'active'")

    def get_active_labor_count(self) -> int:
        """Get count of active Labor accounts."""
        return self.labor_repo.count("status = 'active'")
