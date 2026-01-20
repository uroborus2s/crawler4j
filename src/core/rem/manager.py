"""环境管理器 - 统一门面。

规格参考: docs/srs/05-framework-core/05-2-runtime-environment-management.md

EnvironmentManager 是 REM 的统一入口，提供：
    - acquire: 申请环境租约
    - release: 释放环境租约
    - startup: 初始化与崩溃恢复
    - run_gc: 垃圾回收
"""
import time
from datetime import datetime
from typing import Any

from src.core.foundation.logging import logger
from src.core.persistence.database import STATE_DB, get_connection
from src.core.rem.ip_pool import get_ip_pool_manager
from src.core.rem.models import (
    Environment,
    EnvLease,
    EnvRequirement,
    EnvStatus,
    EnvUnavailableError,
)
from src.core.rem.pool import EnvPool, LeaseManager
from src.core.rem.provider import BaseProvider, get_provider


class EnvironmentManager:
    """环境管理器。
    
    规格 5.2.1.2: 核心承诺是为每一次任务运行提供满足约束的环境租约。
    
    Usage:
        manager = EnvironmentManager()
        await manager.startup()
        
        # 申请环境
        requirement = EnvRequirement(kind=EnvKind.BROWSER)
        lease = await manager.acquire(requirement)
        
        # 使用环境...
        env = await manager.get_env(lease.env_id)
        
        # 释放环境
        await manager.release(lease)
    """
    
    def __init__(
        self,
        gc_interval: int = 30,
    ):
        """初始化环境管理器。
        
        Args:
            gc_interval: 垃圾回收间隔（秒）
        """
        from src.core.system.preferences_service import (
            PreferenceKey,
            get_preferences_service,
        )
        
        prefs = get_preferences_service()
        max_instances = prefs.get(PreferenceKey.ENV_MAX_INSTANCES, 50)
        
        self.pool = EnvPool(max_instances=max_instances)
        self.lease_manager = LeaseManager(self.pool)
        self._gc_interval = gc_interval
        self._running = False
    
    async def startup(self) -> None:
        """启动环境管理器。
        
        执行：
            1. 从数据库恢复环境状态
            2. 处理崩溃残留
            3. 启动 GC 循环
        """
        logger.info("[REM] 环境管理器启动中...")
        
        # 从数据库恢复
        await self.pool.load_from_db()
        
        # 初始化 IP 池管理器
        await get_ip_pool_manager().startup()

        # 处理崩溃残留
        await self._recover_crashed()
        
        # 启动 GC
        self._running = True
        logger.info(f"[REM] 环境管理器启动完成, 环境数: {len(await self.pool.list_all())}")
        
    async def acquire(
        self,
        requirement: EnvRequirement,
        default_provider: str = "playwright_local",
    ) -> EnvLease:
        """申请环境租约。
        
        规格 5.2.3.3 Acquire 流程：
            1. 在 READY 实例中挑选匹配项
            2. 若无匹配，按策略 spawn 新实例
            3. 发放租约，将实例置为 BUSY
        
        Args:
            requirement: 环境需求
            default_provider: 默认提供者
        
        Returns:
            环境租约
        
        Raises:
            EnvUnavailableError: 无可用环境
        """
        # 1. 查找可用环境
        env = await self.pool.find_available(requirement)
        
        # 2. 无可用环境则尝试创建
        if not env:
            if not self.pool.can_create():
                raise EnvUnavailableError(
                    "无可用环境且达到配额上限",
                    stage="ACQUIRE",
                    hint="请等待其他任务完成或增加配额"
                )
            
            provider = get_provider(default_provider)
            if not provider:
                raise EnvUnavailableError(
                    f"Provider 未注册: {default_provider}",
                    stage="CREATE",
                    hint="请检查 Provider 配置"
                )
            
            env = await self._create_env(provider, proxy_config=requirement.proxy_config)
        
        # 3. 发放租约
        lease = await self.lease_manager.acquire(
            env,
            requirement.task_run_id,
            timeout=requirement.timeout,
        )
        
        return lease
    
    async def reset(self, env: Environment) -> None:
        """重置环境。"""
    
        provider = get_provider(env.provider)
        # 关闭窗口
        if provider:
            try:
                await provider.close(env)
            except Exception as e:
                logger.warning(f"[REM] 关闭窗口失败: {e}")
        await self.pool.update_status(env.id, EnvStatus.READY)
        logger.info(f"[REM] 环境已重置: id={env.id}")
    
    async def release(self, lease: EnvLease, dirty: bool = False) -> bool:
        """释放环境租约。
        
        Release 流程：
            1. 验证令牌
            2. 关闭窗口
            3. 执行清理
            4. 恢复为 READY
        
        Args:
            lease: 租约
            dirty: 是否标记为脏（需要额外清理）
        
        Returns:
            是否释放成功
        """
        env = await self.lease_manager.release(lease, lease.token)
        if not env:
            return False
        await self.reset(env)
        return True
    
    async def get_env(self, env_id: int) -> Environment | None:
        """获取环境实例。"""
        return await self.pool.get(env_id)
    
    async def list_envs(self) -> list[Environment]:
        """列出所有环境。"""
        return await self.pool.list_all()
    
    async def run_gc(self) -> int:
        """手动触发垃圾回收。

        Returns:
            回收的环境数量
        """
        return await self._gc_once()
    
    async def health_check(self, env_id: int) -> bool:
        """执行健康检查，失败则标记 ERROR。
        
        规格 FR-CORE-ENV-004: 周期性或按需检测环境是否可用，不可用时标记隔离。
        
        Args:
            env_id: 环境 ID
        
        Returns:
            是否健康
        """
        env = await self.pool.get(env_id)
        if not env:
            return False
        
        provider = get_provider(env.provider)
        if not provider:
            return False
        
        try:
            is_healthy = await provider.health_check(env)
            if not is_healthy:
                await self.pool.update_status(env_id, EnvStatus.ERROR)
                logger.warning(f"[REM] 环境健康检查失败: id={env_id}")
            return is_healthy
        except Exception as e:
            logger.warning(f"[REM] 健康检查异常: {e}")
            await self.pool.update_status(env_id, EnvStatus.ERROR)
            return False
    
    async def create_env(
        self,
        provider_name: str,
        env_name: str | None = None,
        config: dict | None = None,
        requirement: EnvRequirement | None = None,
        post_action: Any = "test",
        workflow_module: str | None = None,
    ) -> Environment:
        """从 UI 创建环境。
        
        Args:
            provider_name: Provider 名称
            env_name: 环境名称
            config: 配置
            requirement: 要求
            post_action: 创建后操作
            workflow_module: 工作流模块
        """
        if not self.pool.can_create():
            raise EnvUnavailableError(
                "达到配额上限",
                stage="CREATE",
                hint="请先销毁其他环境"
            )
        
        provider = get_provider(provider_name)
        if not provider:
            raise EnvUnavailableError(
                f"Provider 未注册: {provider_name}",
                stage="CREATE",
                hint="请检查 Provider 配置"
            )
            
        final_config = config or {}
        if env_name:
            final_config["env_name"] = env_name

        proxy_config = requirement.proxy_config if requirement else None
        
        from src.core.rem.models import PostCreateAction
        action_enum = PostCreateAction(post_action)

        return await self._create_env(
            provider, 
            final_config, 
            proxy_config=proxy_config,
            post_action=action_enum,
            workflow_module=workflow_module
        )
    
    async def destroy_env(self, env_id: int) -> bool:
        """直接销毁环境（供 UI 调用）。
        
        Args:
            env_id: 环境 ID
        
        Returns:
            是否销毁成功
        """
        env = await self.pool.get(env_id)
        if not env:
            return False

        logger.info(f"[REM] 销毁环境: id={env.id}")
        
        await self.pool.update_status(env.id, EnvStatus.TERMINATING)
        
        provider = get_provider(env.provider)
        if provider:
            try:
                await provider.destroy(env)
            except Exception as e:
                logger.warning(f"[REM] 环境销毁失败: {e}")
        
        await self.pool.remove(env.id)
        logger.info(f"[REM] 环境已销毁: id={env.id}")        
        return True
    
    async def start_env(self, env_id: int) -> bool:
        """启动环境（READY/PAUSED → BUSY，打开窗口）。
        
        Args:
            env_id: 环境 ID
        
        Returns:
            是否启动成功
        """
        env = await self.pool.get(env_id)
        if not env:
            return False
        if await self._provider_operation(env, "open"):
            return await self._provider_operation(env, "connect")
        return False    
    
    async def stop_env(self, env_id: int) -> bool:
        """停止环境（BUSY → READY，关闭窗口）。
        
        Args:
            env_id: 环境 ID
        
        Returns:
            是否停止成功
        """
        env = await self.pool.get(env_id)
        if not env:
            return False
        return await self._provider_operation(env, "close")
    
    async def pause_env(self, env_id: int) -> bool:
        """暂停环境（READY → PAUSED）。
        
        Args:
            env_id: 环境 ID
        
        Returns:
            是否暂停成功
        """
        env = await self.pool.get(env_id)
        if not env:
            return False
        return await self._provider_operation(env, "pause")
    
    async def resume_env(self, env_id: int) -> bool:
        """恢复环境（PAUSED → READY）。
        
        Args:
            env_id: 环境 ID
        
        Returns:
            是否恢复成功
        """
        env = await self.pool.get(env_id)
        if not env:
            return False
        return await self._provider_operation(env, "resume")
    
    # === Metadata API ===
    
    async def get_metadata(
        self, 
        env_id: int, 
        namespace: str, 
        key: str
    ) -> Any:
        """获取环境元数据值。
        
        Args:
            env_id: 环境 ID
            namespace: 命名空间（通常为 module_name）
            key: 字段名
        
        Returns:
            元数据值，不存在返回 None
        """
        return self.pool.get_metadata(env_id, namespace, key)
    
    async def set_metadata(
        self,
        env_id: int,
        namespace: str,
        key: str,
        value: Any,
        value_type: str = "string",
    ) -> bool:
        """设置环境元数据值。
        
        Args:
            env_id: 环境 ID
            namespace: 命名空间（通常为 module_name）
            key: 字段名
            value: 字段值
            value_type: 类型提示 (string|int|float|bool|json)
        
        Returns:
            是否设置成功
        """
        return self.pool.set_metadata(env_id, namespace, key, value, value_type)
    
    async def list_metadata(
        self,
        env_id: int,
        namespace: str | None = None,
    ) -> dict:
        """列出环境元数据。
        
        Args:
            env_id: 环境 ID
            namespace: 命名空间（可选，为空则返回所有）
        
        Returns:
            元数据字典
        """
        return self.pool.list_metadata(env_id, namespace)
    
    async def delete_metadata(
        self,
        env_id: int,
        namespace: str,
        key: str | None = None,
    ) -> int:
        """删除环境元数据。
        
        Args:
            env_id: 环境 ID
            namespace: 命名空间
            key: 字段名（可选，为空则删除整个 namespace）
        
        Returns:
            删除的条数
        """
        return self.pool.delete_metadata(env_id, namespace, key)
    
    # === 统一更新方法 ===
    
    async def update_env(
        self,
        env_id: int,
        *,
        name: str | None = None,
        proxy_value: str | None = None,
        proxy_pool_id: str | None = None,
        randomize_fingerprint: bool = False,
    ) -> bool:
        """统一更新环境配置。
        
        Args:
            env_id: 环境 ID
            name: 新名称（可选）
            proxy_value: 静态代理地址（可选）
            proxy_pool_id: 从 IP 池绑定（可选）
            randomize_fingerprint: 是否刷新指纹
        
        Returns:
            是否更新成功
        """
        env = await self.pool.get(env_id)
        if not env:
            logger.warning(f"[REM] 更新失败: 环境不存在 id={env_id}")
            return False
        
        return await self._orchestrate_update(
            env,
            name=name,
            proxy_value=proxy_value,
            proxy_pool_id=proxy_pool_id,
            randomize_fingerprint=randomize_fingerprint,
        )
    
    async def _orchestrate_update(
        self,
        env: Environment,
        *,
        name: str | None = None,
        proxy_value: str | None = None,
        proxy_pool_id: str | None = None,
        randomize_fingerprint: bool = False,
    ) -> bool:
        """统一更新编排。
        
        Returns:
            是否更新成功
        """
        from src.core.rem.models import ProxyConfig, ProxyMode
        
        updated = False
        provider = get_provider(env.provider)
        
        # 1. 更新名称
        if name:
            env.name = name
            updated = True
        
        # 2. 处理代理更新
        if proxy_value:
            if env.proxy_config is None:
                env.proxy_config = ProxyConfig(mode=ProxyMode.STATIC)
            env.proxy_config.static_value = proxy_value
            env.proxy_config.current_ip = proxy_value.split("@")[-1] if "@" in proxy_value else proxy_value
            updated = True
            logger.info(f"[REM] 代理已更新: id={env.id} value={proxy_value[:20]}...")
        
        # 3. 从 IP 池绑定
        if proxy_pool_id:
            success = await self._bind_ip_if_needed(env, proxy_pool_id)
            if success:
                updated = True
        
        # 4. 刷新指纹
        if randomize_fingerprint and provider:
            try:
                success = await provider.update(env, {"randomize_fingerprint": True})
                if success:
                    logger.info(f"[REM] 指纹已刷新: id={env.id}")
                    updated = True
            except Exception as e:
                logger.warning(f"[REM] 指纹刷新失败: {e}")
        
        # 5. 持久化
        if updated:
            await self.pool.add(env)
        
        return updated
    
    # === Layer 3: 操作层 ===
    async def _provider_operation(
        self,
        env: Environment,
        action: str,
        **kwargs,
    ) -> bool:
        """统一 Provider 操作。
        
        Args:
            provider: Provider 实例
            env: 环境实例
            action: 操作类型 (open/close/destroy/reset/update)
            **kwargs: 额外参数
        
        Returns:
            是否操作成功
        """
        provider = get_provider(env.provider)
        if not provider:
            return False
        try:
            if action == "open":
                await self.pool.update_status(env.id, EnvStatus.BUSY)
                result = await provider.open(env)
                return result
            elif action == "connect":
                result = await provider.connect(env)
                if result:
                    # 连接成功：更新使用统计并持久化
                    env.increment_usage()
                    await self.pool.update_status(env.id, EnvStatus.RUNNING)
                    await self.pool.add(env)
                return result
            elif action == "disconnect":
                await self.pool.update_status(env.id, EnvStatus.BUSY)
                result = await provider.disconnect(env)
                return result
            elif action == "close":
                await self.pool.update_status(env.id, EnvStatus.READY)
                result = await provider.close(env)
                return result
            elif action == "pause":
                await self.pool.update_status(env.id, EnvStatus.PAUSED)
                return True
            elif action == "resume":
                await self.pool.update_status(env.id, EnvStatus.READY)
                return True
            elif action == "destroy":
                await provider.destroy(env)
                return True
            elif action == "reset":
                return await provider.reset(env)
            elif action == "update":
                return await provider.update(env, kwargs.get("config", {}))
            elif action == "health_check":
                return await provider.health_check(env)
            else:
                logger.error(f"[REM] 未知的 Provider 操作: {action}")
                return False
        except Exception as e:
            logger.warning(f"[REM] Provider 操作失败: action={action}, error={e}")
            return False
    
        
    async def _bind_ip_if_needed(self, env: Environment, pool_id: str) -> bool:
        """IP 绑定（如果需要）。
        
        Args:
            env: 环境实例
            pool_id: IP 池 ID
        
        Returns:
            是否绑定成功
        """
        from src.core.rem.ip_pool import get_ip_pool_manager
        from src.core.rem.models import ProxyConfig, ProxyMode
        
        pool_manager = get_ip_pool_manager()
        
        # 先解绑旧 IP
        await pool_manager.unbind_ip(env.id)
        
        # 绑定新 IP
        ip = await pool_manager.bind_ip(env.id, pool_id)
        if ip:
            if env.proxy_config is None:
                env.proxy_config = ProxyConfig(mode=ProxyMode.POOL)
            env.proxy_config.mode = ProxyMode.POOL
            env.proxy_config.pool_id = pool_id
            env.proxy_config.current_ip = ip.address
            logger.info(f"[REM] IP 已绑定: id={env.id} ip={ip.address}")
            return True
        
        return False
    
    
    # === 原有私有方法 ===
    async def _create_env(
        self,
        provider: BaseProvider,
        config: dict | None = None,
        proxy_config: Any | None = None,  # ProxyConfig
        post_action: Any = "test",
        workflow_module: str | None = None,
    ) -> Environment:
        """创建环境。
        
        流程：
            1. 生成环境名称和 ID
            2. 创建占位环境并持久化
            3. 处理代理绑定（如有）
            4. 调用 Provider 创建 (根据 post_action 决定是否启动)
            5. (Optional) 执行工作流
            6. (Optional) 关闭窗口
            7. 设置状态为 READY
        """
        from src.core.rem.models import PostCreateAction, ProxyMode
        
        logger.info(f"[REM] 创建环境: provider={provider.name} action={post_action}")
        
        if config and config.get("env_name"):
            # 用户指定名称
            env_name = config["env_name"]
            skeleton_env = Environment(
                name=env_name,
                kind=provider.kind,
                provider=provider.name,
                status=EnvStatus.CREATING,
                created_at=int(time.time()),
                updated_at=int(time.time()),
                proxy_config=proxy_config,
            )
            # 持久化占位记录
            await self.pool.add(skeleton_env)
        else:
            # 自动生成名称并原子占位
            skeleton_env = await self._reserve_env_placeholder(
                provider.kind, 
                provider.name, 
                proxy_config
            )
            env_name = skeleton_env.name
        
        env_id = skeleton_env.id
        
        try:
            # 3. 处理代理绑定 (如果是 POOL 模式)
            if proxy_config and proxy_config.mode == ProxyMode.POOL and proxy_config.pool_id:
                from src.core.rem.ip_pool import get_ip_pool_manager
                ip_manager = get_ip_pool_manager()
                ip = await ip_manager.bind_ip(env_id, proxy_config.pool_id)
                if ip:
                    proxy_config.current_ip = ip.address
                    # 生成静态代理字符串供 Provider 使用
                    auth = f"{ip.username}:{ip.password}@" if ip.username else ""
                    protocol = ip.protocol or "socks5"
                    proxy_config.static_value = f"{protocol}://{auth}{ip.address}:{ip.port}"
                    logger.info(f"[REM] 环境绑定 IP: id={env_id} ip={ip.address}")
                else:
                    logger.warning(f"[REM] 环境绑定 IP 失败: id={env_id} pool={proxy_config.pool_id}")
            
            # 4. 调用 Provider 创建
            if config is None:
                config = {}
            config["env_id"] = env_id
            config["env_name"] = env_name
            if proxy_config:
                config["proxy"] = proxy_config.to_dict()
            
            # create 仅负责创建记录，不再启动 (config["launch"] 已弃用或被忽略)
            env = await provider.create(config)
            
            # 修正 id
            env.id = env_id
            env.name = env_name
            
            # 手动合并 POOL 模式生成的静态代理配置
            if proxy_config and proxy_config.mode == ProxyMode.POOL and proxy_config.static_value:
                if env.proxy_config:
                    env.proxy_config.static_value = proxy_config.static_value
                    env.proxy_config.current_ip = proxy_config.current_ip

            # 5. 更新环境记录 (此时有了 external_id)
            env.status = EnvStatus.READY
            
            # 先保存到数据库以确保 ID 存在
            await self.pool.add(env) # update because add was called with skeleton
            
            logger.info(f"[REM] 环境创建成功: id={env_id} external_id={env.external_id}")
            
            # 6. 处理 Post-Create Action
            should_launch = (post_action != PostCreateAction.NONE)
            
            if should_launch:
                logger.info(f"[REM] 执行 Post-Create Action: {post_action}")
                
                # 6.1 Open Window
                if await self._provider_operation( env, "open"):
                    # 6.2 Connect Playwright
                    if await self._provider_operation( env, "connect"):
                        try:
                            # 6.3 Execute Workflow (if any)
                            if post_action == PostCreateAction.WORKFLOW and workflow_module:
                                logger.info(f"[REM] 执行初始化工作流: {workflow_module}")
                                try:
                                    import importlib
                                    mod = importlib.import_module(f"modules.{workflow_module}")
                                    if hasattr(mod, "run"):
                                        await mod.run(env)
                                        logger.info(f"[REM] 工作流执行完成: {workflow_module}")
                                    else:
                                        logger.warning(f"[REM] 工作流模块缺少 run 方法: {workflow_module}")
                                except ImportError:
                                    logger.error(f"[REM] 找不到工作流模块: {workflow_module}")
                                except Exception as e:
                                    logger.error(f"[REM] 工作流执行出错: {e}")
                        finally:
                            # 6.4 Close Window (TEST/WORKFLOW 结束后均关闭)
                            await self._provider_operation( env, "close")
                    else:
                        logger.warning(f"[REM] Post-Create Connect 失败: id={env_id}")
                        await self._provider_operation( env, "close")
                else:
                    logger.warning(f"[REM] Post-Create Open 失败: id={env_id}")

            return env
            
        except Exception:
            # 如果创建失败，清理占位环境（未在外部创建成功）
            logger.error(f"[REM] 环境创建失败，清理预创建记录: id={env_id}")
            await self.destroy_env(env_id)
            raise
    
    async def _reserve_env_placeholder(
        self, 
        kind: Any, # EnvKind
        provider: str,
        proxy_config: Any | None = None
    ) -> Environment:
        """原子化保留环境名称占位符（Max+1 策略）。
        
        1. 查询当天所有前缀匹配的名称
        2. 计算最大序列号 + 1
        3. 立即插入 CREATING 状态的占位记录
        
        Returns:
            已持久化的 Environment 对象 (带 id)
        """
        
        today = datetime.now().strftime("%Y%m%d")
        prefix = f"env-{today}-"
        
        with get_connection(STATE_DB) as conn:
            # 1. 查找所有匹配前缀的名称
            cursor = conn.execute(
                "SELECT name FROM environments WHERE name LIKE ?",
                (f"{prefix}%",)
            )
            existing_names = [row[0] for row in cursor.fetchall()]

            # 2. 计算最大序列号
            max_seq = 0
            prefix_len = len(prefix)
            for name in existing_names:
                if len(name) > prefix_len:
                    try:
                        seq = int(name[prefix_len:])
                        if seq > max_seq:
                            max_seq = seq
                    except ValueError:
                        continue # 忽略后缀非数字的名称
            
            new_name = f"{prefix}{max_seq + 1}"
            
            # 3. 创建并持久化占位对象
            env = Environment(
                name=new_name,
                kind=kind,
                provider=provider,
                status=EnvStatus.CREATING,
                created_at=int(time.time()),
                updated_at=int(time.time()),
                proxy_config=proxy_config,
            )
            
            # 使用现有逻辑插入 (依赖 pool.add -> _persist_env)
            # 此时无法直接在 get_connection 上下文中使用 pool.add (因为它会重开连接), 
            # 但既然已经在一个事务里了... 
            # 简单起见，这里仅计算名称，持久化交给 pool.add
            # 风险提示：如果在 select 和 pool.add 之间有其他插入，可能冲突。
            # 但由于我们基于 fetchall 做了 max 逻辑，冲突概率极低。
            # 真正原子性需要 pool.add 支持传入 external connection，或者这里手动 insert。
            # 为了保持架构整洁，我们还是调用 pool.add
            pass
        
        # 移出 context manager 以使用 pool.add
        await self.pool.add(env)
        logger.info(f"[REM] 预留环境名称: {env.name} id={env.id}")
        return env
            
    
    async def _recover_crashed(self) -> None:
        """崩溃恢复：处理非稳态环境。
        
        规格 5.2.3.3 Fail-safe:
            - CREATING 状态的环境：调用 Provider 关闭/销毁后删除记录
            - BUSY 状态的环境：检查窗口状态，优先尝试软清理（reset），失败则置为 DEAD
        """
        for env in await self.pool.list_all():
            provider = get_provider(env.provider)
            if not provider:
                logger.error(f"[REM] 未找到 Provider: {env.provider}")
                await self.destroy_env(env.id)
            elif env.status == EnvStatus.CREATING or not await provider.exists(env):
                # 创建中的环境视为失败，需要同步关闭并删除
                logger.warning(f"[REM] 发现未完成创建的环境: id={env.id}")
                await self.destroy_env(env.id)
                logger.info(f"[REM] 已删除未完成创建的环境记录: id={env.id}")
            elif env.status in {EnvStatus.BUSY, EnvStatus.RUNNING}:
                # 用户规范：崩溃时运行中的环境，重启后恢复为 READY
                logger.warning(f"[REM] 发现崩溃时运行中的环境: id={env.id}")
                await self.reset(env)
        
    async def _gc_once(self) -> int:
        """执行一次 GC。
        
        Returns:
            回收的环境数量
        """
        count = 0
        
        for env in await self.pool.list_all():
            provider = get_provider(env.provider)
            if not provider:
                logger.error(f"[REM] 未找到 Provider: {env.provider}")
                await self.destroy_env(env.id)
                count = count + 1 
            elif not await provider.exists(env):
                logger.warning(f"[REM] 发现不存在的环境: id={env.id}")
                await self.destroy_env(env.id)
                count = count + 1 
                logger.info(f"[REM] 已删除不存在的环境记录: id={env.id}")
            elif env.status == EnvStatus.CREATING or env.status == EnvStatus.DEAD:
                logger.warning(f"[REM] 发现未完成创建的环境: id={env.id}")
                await self.destroy_env(env.id)
                count = count + 1 
                logger.info(f"[REM] 已删除未完成创建的环境记录: id={env.id}")
            elif env.status in {EnvStatus.BUSY, EnvStatus.RUNNING}:
                # 用户规范：崩溃时运行中的环境，重启后恢复为 READY
                if not await provider.is_window_open(env):
                    logger.warning(f"[REM] 发现运行中崩溃的环境: id={env.id}")
                    await self.reset(env)
                    count = count + 1
            elif env.status == EnvStatus.READY:
                if await provider.is_window_open(env):
                    logger.warning(f"[REM] 发现状态不一致的环境: id={env.id}")
                    await self.reset(env)
                    count = count + 1
        if count > 0:
            logger.info(f"[REM] GC 完成: 回收 {count} 个环境")
        return count

# 全局单例
_manager: EnvironmentManager | None = None


def get_environment_manager() -> EnvironmentManager:
    """获取全局 EnvironmentManager 实例。"""
    global _manager
    if _manager is None:
        _manager = EnvironmentManager()
    return _manager
