"""环境生命周期管理模块。

统一管理环境的创建和销毁逻辑，支持自动和手动两种触发方式。
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

from src.core.browser_api import BrowserAPI
from src.core.models.ctrip_account import CtripAccount
from src.core.models.environment import Environment, EnvironmentStatus
from src.core.models.labor_account import LaborAccount
from src.utils.fingerprint_generator import FingerprintGenerator
from src.utils.logger import logger
from src.utils.storage import (
    CtripAccountRepository,
    EnvironmentRepository,
    LaborAccountRepository,
    ProxyIPRepository,
)


class DestroyReason(Enum):
    """环境销毁原因。"""

    MANUAL = auto()  # 用户手动删除
    BLACKLISTED = auto()  # 携程账号被封禁
    ERROR = auto()  # 环境异常


@dataclass
class CreateEnvironmentParams:
    """环境创建参数。"""

    name: str | None = None
    ctrip_account_id: int | None = None
    labor_account_id: int | None = None
    proxy_ip_id: int | None = None
    proxy_config: dict[str, Any] | None = None
    fingerprint_config: dict[str, Any] | None = None
    group_id: str | None = None
    daily_open_limit: int = 0
    remark: str = ""


class EnvironmentManager:
    """统一环境生命周期管理。

    功能：
    - create_environment(): 统一创建流程
    - destroy_environment(): 统一销毁流程

    使用方式：
    - 自动模式：调度器调用 create_environment() / destroy_environment()
    - 手动模式：UI 页面调用相同方法
    """

    def __init__(self):
        self.env_repo = EnvironmentRepository()
        self.ctrip_repo = CtripAccountRepository()
        self.labor_repo = LaborAccountRepository()
        self.proxy_repo = ProxyIPRepository()

    # ==================== 创建环境 ====================

    def create_environment(
        self,
        params: CreateEnvironmentParams | None = None,
        auto_assign: bool = False,
    ) -> Environment | None:
        """统一环境创建流程。

        Args:
            params: 创建参数（手动模式使用）
            auto_assign: 是否自动分配账号（调度器使用）

        Returns:
            创建成功返回 Environment，失败返回 None
        """
        from src.config import config

        params = params or CreateEnvironmentParams()

        # === Step 1: 分配携程账号 ===
        ctrip_account = self._assign_ctrip_account(params.ctrip_account_id, auto_assign)
        if not ctrip_account:
            logger.warning("没有可用的携程账号")
            return None

        # 注意：劳保账号不在创建环境时分配，而是在运行时动态获取

        # === Step 2: 分配代理IP（可选）===
        proxy_ip_id = params.proxy_ip_id
        proxy_config = params.proxy_config

        if auto_assign and not proxy_ip_id:
            proxy_data = self.proxy_repo.get_least_used()
            if proxy_data:
                proxy_ip_id = proxy_data["id"]
                proxy_config = {
                    "type": proxy_data.get("protocol", "http"),
                    "host": proxy_data["ip"],
                    "port": proxy_data["port"],
                    "user": proxy_data.get("user"),
                    "pass": proxy_data.get("password"),
                }

        # === Step 3: 创建远程浏览器配置 ===
        try:
            profile_name = params.name or f"Auto_{ctrip_account.phone_number[-4:]}"
            remark = (
                params.remark
                or f"Created by Crawler4j [Ctrip: {ctrip_account.phone_number}]"
            )
            fingerprint = params.fingerprint_config or FingerprintGenerator.generate()

            profile_id = BrowserAPI.create_profile(
                name=profile_name,
                remark=remark,
                proxy=proxy_config,
                fingerprint=fingerprint,
                group_id=params.group_id,
            )

            logger.info(f"✅ 创建浏览器配置: {profile_id}")

        except Exception as e:
            logger.error(f"创建浏览器配置失败: {e}")
            return None

        # === Step 4: 更新使用计数 ===
        try:
            if proxy_ip_id:
                self.proxy_repo.increment_usage(proxy_ip_id)

            # === Step 5: 保存本地环境记录 ===
            env_id = self.env_repo.create(
                ctrip_account_id=ctrip_account.id,
                labor_account_id=None,  # 劳保账号在运行时动态分配
                browser_profile_id=profile_id,
                browser_type=config.browser_type,
                proxy_ip_id=proxy_ip_id,
                daily_open_limit=params.daily_open_limit,
            )

            # === Step 6: 更新携程账号状态 ===
            if ctrip_account.id:
                self.ctrip_repo.update_status(ctrip_account.id, "active")

            logger.info(
                f"✅ 环境创建成功: ENV-{env_id} (携程: {ctrip_account.phone_number})"
            )

            # === Step 7: 发送事件通知 ===
            from src.core.events import EventType, get_event_bus

            bus = get_event_bus()
            bus.emit(
                EventType.ENVIRONMENT_CREATED,
                {
                    "env_id": env_id,
                    "ctrip_phone": ctrip_account.phone_number,
                },
            )

            return Environment(
                id=env_id,
                ctrip_account_id=ctrip_account.id or 0,
                labor_account_id=0,  # 劳保账号在运行时动态分配
                browser_profile_id=profile_id,
                status=EnvironmentStatus.IDLE,
            )

        except Exception as e:
            logger.error(f"保存环境记录失败: {e}")
            # 回滚：删除已创建的浏览器配置
            try:
                BrowserAPI.delete_profile(profile_id)
            except Exception:
                pass
            # 回滚：恢复代理使用计数
            if proxy_ip_id:
                self.proxy_repo.decrement_usage(proxy_ip_id)
            return None

    async def create_environment_async(
        self,
        params: CreateEnvironmentParams | None = None,
        auto_assign: bool = False,
    ) -> Environment | None:
        """异步版本的环境创建流程（支持接码平台）。

        调度器应使用此方法以支持异步接码平台调用。
        """
        # No import needed here anymore

        params = params or CreateEnvironmentParams()

        # === Step 1: 异步分配携程账号（支持接码平台）===
        ctrip_account = await self._assign_ctrip_account_async(
            params.ctrip_account_id, auto_assign
        )
        if not ctrip_account:
            logger.warning("没有可用的携程账号")
            return None

        # === Step 2-7: Re-use logic but asynchronous
        return await self._create_environment_with_account_async(params, ctrip_account, auto_assign)

    async def _create_environment_with_account_async(
        self,
        params: CreateEnvironmentParams,
        ctrip_account: CtripAccount,
        auto_assign: bool,
    ) -> Environment | None:
        """使用已分配的携程账号创建环境（异步非阻塞版本）。"""
        from src.config import config
        from src.core.events import EventType, get_event_bus
        from src.utils.async_utils import run_blocking

        proxy_ip_id = params.proxy_ip_id
        proxy_config = params.proxy_config

        if auto_assign and not proxy_ip_id:
            # DB read - fast enough to run in thread or even sync if WAL is on, 
            # but let's be safe and put it in thread if it were complex. 
            # get_least_used is a simple query.
            # For strictness:
            proxy_data = await run_blocking(self.proxy_repo.get_least_used)
            if proxy_data:
                proxy_ip_id = proxy_data["id"]
                proxy_config = {
                    "type": proxy_data.get("protocol", "http"),
                    "host": proxy_data["ip"],
                    "port": proxy_data["port"],
                    "user": proxy_data.get("user"),
                    "pass": proxy_data.get("password"),
                }

        try:
            profile_name = params.name or f"Auto_{ctrip_account.phone_number[-4:]}"
            remark = (
                params.remark
                or f"Created by Crawler4j [Ctrip: {ctrip_account.phone_number}]"
            )
            fingerprint = params.fingerprint_config or FingerprintGenerator.generate()

            # True Async Call
            profile_id = await BrowserAPI.create_profile_async(
                name=profile_name,
                remark=remark,
                proxy=proxy_config,
                fingerprint=fingerprint,
                group_id=params.group_id,
            )

            logger.info(f"✅ 创建浏览器配置 (Async): {profile_id}")

        except Exception as e:
            logger.error(f"创建浏览器配置失败: {e}")
            return None

        try:
            # BLOCKING DB CALLS -> Wrapped
            def _save_env_record():
                if proxy_ip_id:
                    self.proxy_repo.increment_usage(proxy_ip_id)

                eid = self.env_repo.create(
                    ctrip_account_id=ctrip_account.id,
                    labor_account_id=None,
                    browser_profile_id=profile_id,
                    browser_type=config.browser_type,
                    proxy_ip_id=proxy_ip_id,
                    daily_open_limit=params.daily_open_limit,
                )
                if ctrip_account.id:
                    self.ctrip_repo.update_status(ctrip_account.id, "active")
                return eid

            env_id = await run_blocking(_save_env_record)

            logger.info(
                f"✅ 环境创建成功: ENV-{env_id} (携程: {ctrip_account.phone_number})"
            )

            # Event emission is thread-safe in PyQt usually if connected via slots,
            # but here we are in a thread? No, run_blocking returns to main loop.
            # We are back in the main loop here!
            bus = get_event_bus()
            bus.emit(
                EventType.ENVIRONMENT_CREATED,
                {"env_id": env_id, "ctrip_phone": ctrip_account.phone_number},
            )

            return Environment(
                id=env_id,
                ctrip_account_id=ctrip_account.id or 0,
                labor_account_id=0,
                browser_profile_id=profile_id,
                status=EnvironmentStatus.IDLE,
            )

        except Exception as e:
            logger.error(f"保存环境记录失败: {e}")
            # Rollback
            try:
                await BrowserAPI.delete_profile_async(profile_id)
            except Exception:
                pass
            if proxy_ip_id:
                # Fire and forget rollback or await? Await to be safe
                await run_blocking(self.proxy_repo.decrement_usage, proxy_ip_id)
            return None

    def _create_environment_with_account(
        self,
        params: CreateEnvironmentParams,
        ctrip_account: CtripAccount,
        auto_assign: bool,
    ) -> Environment | None:
        """使用已分配的携程账号创建环境（公共逻辑）。"""
        from src.config import config

        proxy_ip_id = params.proxy_ip_id
        proxy_config = params.proxy_config

        if auto_assign and not proxy_ip_id:
            proxy_data = self.proxy_repo.get_least_used()
            if proxy_data:
                proxy_ip_id = proxy_data["id"]
                proxy_config = {
                    "type": proxy_data.get("protocol", "http"),
                    "host": proxy_data["ip"],
                    "port": proxy_data["port"],
                    "user": proxy_data.get("user"),
                    "pass": proxy_data.get("password"),
                }

        try:
            profile_name = params.name or f"Auto_{ctrip_account.phone_number[-4:]}"
            remark = (
                params.remark
                or f"Created by Crawler4j [Ctrip: {ctrip_account.phone_number}]"
            )
            fingerprint = params.fingerprint_config or FingerprintGenerator.generate()

            profile_id = BrowserAPI.create_profile(
                name=profile_name,
                remark=remark,
                proxy=proxy_config,
                fingerprint=fingerprint,
                group_id=params.group_id,
            )

            logger.info(f"✅ 创建浏览器配置: {profile_id}")

        except Exception as e:
            logger.error(f"创建浏览器配置失败: {e}")
            return None

        try:
            if proxy_ip_id:
                self.proxy_repo.increment_usage(proxy_ip_id)

            env_id = self.env_repo.create(
                ctrip_account_id=ctrip_account.id,
                labor_account_id=None,
                browser_profile_id=profile_id,
                browser_type=config.browser_type,
                proxy_ip_id=proxy_ip_id,
                daily_open_limit=params.daily_open_limit,
            )

            if ctrip_account.id:
                self.ctrip_repo.update_status(ctrip_account.id, "active")

            logger.info(
                f"✅ 环境创建成功: ENV-{env_id} (携程: {ctrip_account.phone_number})"
            )

            from src.core.events import EventType, get_event_bus

            bus = get_event_bus()
            bus.emit(
                EventType.ENVIRONMENT_CREATED,
                {"env_id": env_id, "ctrip_phone": ctrip_account.phone_number},
            )

            return Environment(
                id=env_id,
                ctrip_account_id=ctrip_account.id or 0,
                labor_account_id=0,
                browser_profile_id=profile_id,
                status=EnvironmentStatus.IDLE,
            )

        except Exception as e:
            logger.error(f"保存环境记录失败: {e}")
            try:
                BrowserAPI.delete_profile(profile_id)
            except Exception:
                pass
            if proxy_ip_id:
                self.proxy_repo.decrement_usage(proxy_ip_id)
            return None

    def _assign_ctrip_account(
        self, ctrip_id: int | None, auto_assign: bool
    ) -> CtripAccount | None:
        """分配携程账号（同步版本，不支持接码平台）。

        优先级：
        1. 手动指定的账号
        2. 现有未绑定的 active 账号
        """
        if ctrip_id:
            data = self.ctrip_repo.get_by_id(ctrip_id)
            return CtripAccount.from_dict(data) if data else None

        if auto_assign:
            for acc_data in self.ctrip_repo.get_active():
                existing = self.env_repo.get_by_ctrip_account(acc_data["id"])
                if not existing:
                    return CtripAccount.from_dict(acc_data)

        return None

    async def _assign_ctrip_account_async(
        self, ctrip_id: int | None, auto_assign: bool
    ) -> CtripAccount | None:
        """分配携程账号（异步版本，支持接码平台）。

        优先级：
        1. 手动指定的账号
        2. 现有未绑定的 active 账号
        3. 通过接码平台取号创建新账号
        """
        if ctrip_id:
            data = self.ctrip_repo.get_by_id(ctrip_id)
            return CtripAccount.from_dict(data) if data else None

        if auto_assign:
            for acc_data in self.ctrip_repo.get_active():
                existing = self.env_repo.get_by_ctrip_account(acc_data["id"])
                if not existing:
                    return CtripAccount.from_dict(acc_data)

            # 没有现有账号，尝试通过接码平台取号
            return await self._create_ctrip_account_from_sms_platform_async()

        return None

    def _create_ctrip_account_from_sms_platform(self) -> CtripAccount | None:
        """通过接码平台取号创建新携程账号（同步版本）。
        
        注意：如果在已有事件循环中调用，请使用 _create_ctrip_account_from_sms_platform_async
        """
        import asyncio

        try:
            # 检查是否已在事件循环中
            try:
                loop = asyncio.get_running_loop()
                # 已在事件循环中，不能直接调用同步版本
                logger.warning("在事件循环中调用同步方法，请改用异步版本")
                return None
            except RuntimeError:
                # 没有运行中的循环，可以安全创建新循环
                pass

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(
                    self._create_ctrip_account_from_sms_platform_async()
                )
            finally:
                loop.close()

        except Exception as e:
            logger.error(f"接码平台创建账号失败: {e}")
            return None

    async def _create_ctrip_account_from_sms_platform_async(self) -> CtripAccount | None:
        """通过接码平台取号创建新携程账号（异步版本）。"""
        from src.config import config
        from src.core.events import EventType, get_event_bus
        from src.utils.sms_platform import create_sms_client_from_config
        from src.utils.storage import SettingsRepository

        # 1. 检查每日限制
        settings_repo = SettingsRepository()
        current_count = settings_repo.get_sms_creation_count_today()
        limit = config.daily_auto_env_creation_limit

        if current_count >= limit:
            logger.warning(f"今日接码创建环境已达上限 ({current_count}/{limit})")
            
            # 发送通知事件
            get_event_bus().emit(
                EventType.SMS_CREATION_LIMIT_REACHED, 
                {"current": current_count, "limit": limit}
            )
            return None

        client = create_sms_client_from_config()
        if not client:
            logger.debug("接码平台未配置，无法自动创建账号")
            return None

        try:
            phone = await client.get_phone()

            if not phone:
                logger.warning("接码平台取号失败")
                return None

            logger.info(f"✅ 接码平台取号成功: {phone}")

            # 增加计数
            settings_repo.increment_sms_creation_count()

            from src.config import config

            account_id = self.ctrip_repo.create(
                country_code="+86",
                phone_number=phone,
                password=None,
                account_type="api",
                sms_verify_type="api",
                sms_platform_type=config.sms_platform_host,
                sms_platform_url=f"http://{config.sms_platform_host}",
                sms_platform_key=config.sms_platform_product_id,
            )

            logger.info(f"✅ 创建携程账号记录: ID-{account_id}")

            return CtripAccount(
                id=account_id,
                country_code="+86",
                phone_number=phone,
                account_type="api", # type: ignore
                sms_verify_type="api", # type: ignore
            )

        except Exception as e:
            logger.error(f"接码平台创建账号失败: {e}")
            return None

    def _assign_labor_account(
        self, labor_id: int | None, auto_assign: bool
    ) -> LaborAccount | None:
        """分配劳保账号。"""
        if labor_id:
            # 手动指定
            data = self.labor_repo.get_by_id(labor_id)
            return LaborAccount.from_dict(data) if data else None

        if auto_assign:
            # 自动分配：选择绑定次数最少的
            data = self.labor_repo.get_least_bound()
            return LaborAccount.from_dict(data) if data else None

        return None

    # ==================== 销毁环境 ====================

    def destroy_environment(
        self,
        env_id: int,
        reason: DestroyReason = DestroyReason.MANUAL,
    ) -> bool:
        """统一环境销毁流程。

        Args:
            env_id: 环境 ID
            reason: 销毁原因

        Returns:
            True if successful
        """
        try:
            env_data = self.env_repo.get_by_id(env_id)
            if not env_data:
                logger.warning(f"环境 ENV-{env_id} 不存在")
                return False

            profile_id = env_data.get("browser_profile_id")
            labor_id = env_data.get("labor_account_id")
            proxy_id = env_data.get("proxy_ip_id")
            ctrip_id = env_data.get("ctrip_account_id")

            # === Step 1: 删除远程指纹浏览器配置 ===
            if profile_id:
                try:
                    BrowserAPI.delete_profile(profile_id)
                    logger.info(f"✅ 删除浏览器配置: {profile_id}")
                except Exception as e:
                    logger.warning(f"删除浏览器配置失败: {e}")

            # === Step 2: 释放劳保账号绑定 ===
            if labor_id:
                self.labor_repo.decrement_bind_count(labor_id)
                # 同时释放可能存在的锁定
                self.labor_repo.force_unlock_by_env(env_id)
                logger.debug(f"释放劳保账号绑定: ID-{labor_id}")

            # === Step 3: 释放代理IP使用计数 ===
            if proxy_id:
                self.proxy_repo.decrement_usage(proxy_id)
                logger.debug(f"释放代理IP: ID-{proxy_id}")

            # === Step 4: 恢复携程账号状态 ===
            if ctrip_id:
                self._restore_ctrip_status(ctrip_id, reason)

            # === Step 5: 删除本地环境记录 ===
            self.env_repo.delete(env_id)

            logger.info(f"✅ 环境销毁成功: ENV-{env_id} (原因: {reason.name})")
            return True

        except Exception as e:
            logger.error(f"环境销毁失败: {e}")
            return False

    def destroy_by_ctrip_account(
        self,
        ctrip_account_id: int,
        reason: DestroyReason = DestroyReason.BLACKLISTED,
    ) -> bool:
        """根据携程账号销毁关联环境。

        Args:
            ctrip_account_id: 携程账号 ID
            reason: 销毁原因

        Returns:
            True if successful
        """
        env_data = self.env_repo.get_by_ctrip_account(ctrip_account_id)
        if env_data:
            return self.destroy_environment(env_data["id"], reason)

        # 即使没有环境，也需要更新账号状态
        if reason == DestroyReason.BLACKLISTED:
            self.ctrip_repo.update_status(ctrip_account_id, "blacklisted")
            logger.warning(f"携程账号 ID-{ctrip_account_id} 已标记为 blacklisted")

        return True

    def _restore_ctrip_status(self, ctrip_id: int, reason: DestroyReason) -> None:
        """根据销毁原因恢复携程账号状态。

        - BLACKLISTED: 直接设为 blacklisted
        - MANUAL/ERROR:
            - manual + manual -> idle（可重新使用）
            - 其他 -> blacklisted（需要重新验证）
        """
        if reason == DestroyReason.BLACKLISTED:
            self.ctrip_repo.update_status(ctrip_id, "blacklisted")
            logger.warning(f"携程账号 ID-{ctrip_id} 已标记为 blacklisted")
            return

        # 检查账号类型
        acc = self.ctrip_repo.get_by_id(ctrip_id)
        if not acc:
            return

        acc_type = acc.get("account_type", "manual")
        sms_type = acc.get("sms_verify_type", "manual")

        if acc_type == "manual" and sms_type == "manual":
            self.ctrip_repo.update_status(ctrip_id, "idle")
            logger.info(f"携程账号 ID-{ctrip_id} 状态恢复为 idle")
        else:
            self.ctrip_repo.update_status(ctrip_id, "blacklisted")
            logger.info(f"携程账号 ID-{ctrip_id} 状态设为 blacklisted（非手动账号）")
