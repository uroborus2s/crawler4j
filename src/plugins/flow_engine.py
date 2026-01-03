"""任务流编排执行引擎。

负责按照任务流定义执行任务节点链。
"""

import asyncio
from dataclasses import dataclass

from src.core.events import EventType, get_event_bus
from src.plugins.models import (
    FlowResult,
    TaskConfig,
    TaskContext,
    TaskFlow,
    TaskFlowNode,
    TaskResult,
)
from src.plugins.repositories import TaskConfigRepository, TaskFlowRepository
from src.utils.logger import logger


@dataclass
class ExecutionOptions:
    """执行选项"""
    max_retries: int = 3
    step_timeout: int = 120
    stop_on_error: bool = True


class TaskFlowEngine:
    """任务流编排执行引擎
    
    功能：
    1. 加载和解析任务流定义
    2. 按顺序执行任务节点
    3. 处理成功/失败分支
    4. 支持重试机制
    """

    def __init__(self):
        self.bus = get_event_bus()
        self._task_config_repo = TaskConfigRepository()
        self._task_flow_repo = TaskFlowRepository()
        self._current_flow: TaskFlow | None = None
        self._cancelled = False

    async def execute_flow(
        self,
        flow: TaskFlow,
        ctx: TaskContext,
        options: ExecutionOptions | None = None,
    ) -> FlowResult:
        """执行任务流
        
        Args:
            flow: 任务流定义
            ctx: 执行上下文
            options: 执行选项
            
        Returns:
            FlowResult
        """
        options = options or ExecutionOptions()
        self._current_flow = flow
        self._cancelled = False

        env_id = ctx.env_id
        logger.info(f"[ENV-{env_id}] 🚀 开始执行任务流: {flow.name}")

        if not flow.start_node_id or not flow.nodes:
            return FlowResult(success=False, message="空任务流或无起始节点")

        # 构建节点映射
        node_map = {n.id: n for n in flow.nodes}
        
        if flow.start_node_id not in node_map:
            return FlowResult(success=False, message=f"起始节点不存在: {flow.start_node_id}")

        current_node_id: str | None = flow.start_node_id
        completed_nodes = 0

        while current_node_id and not self._cancelled:
            node = node_map.get(current_node_id)
            if not node:
                logger.error(f"节点不存在: {current_node_id}")
                break

            logger.info(f"[ENV-{env_id}] 📍 执行节点: {node.id}")

            # 执行节点
            result = await self._execute_node(node, ctx, options)

            if result.success:
                completed_nodes += 1
                self.bus.emit(EventType.TASK_PROGRESS, {
                    "env_id": env_id,
                    "node_id": node.id,
                    "completed": completed_nodes,
                    "total": len(flow.nodes),
                })
                current_node_id = node.next_on_success
            else:
                if node.next_on_failure:
                    # 有失败分支，跳转
                    logger.warning(f"节点 {node.id} 失败，跳转到: {node.next_on_failure}")
                    current_node_id = node.next_on_failure
                else:
                    # 无失败分支，中止流程
                    logger.error(f"节点 {node.id} 失败，中止流程: {result.message}")
                    return FlowResult(
                        success=False,
                        completed_nodes=completed_nodes,
                        message=f"节点 {node.id} 失败: {result.message}",
                    )

        if self._cancelled:
            logger.info(f"[ENV-{env_id}] 任务流被取消")
            return FlowResult(
                success=False,
                completed_nodes=completed_nodes,
                message="任务流被取消",
            )

        logger.info(f"[ENV-{env_id}] ✅ 任务流完成，执行了 {completed_nodes} 个节点")
        return FlowResult(
            success=True,
            completed_nodes=completed_nodes,
            message=f"完成 {completed_nodes} 个节点",
        )

    async def _execute_node(
        self,
        node: TaskFlowNode,
        ctx: TaskContext,
        options: ExecutionOptions,
    ) -> TaskResult:
        """执行单个节点，带重试机制"""
        retry_count = node.retry_count or options.max_retries
        last_error: Exception | None = None

        for attempt in range(retry_count + 1):
            if self._cancelled:
                return TaskResult(success=False, message="已取消")

            try:
                # 获取任务配置
                task_config_data = self._task_config_repo.get_with_template(node.task_config_id)
                if not task_config_data:
                    return TaskResult(success=False, message=f"任务配置不存在: {node.task_config_id}")

                task_config = TaskConfig.from_dict(task_config_data)
                plugin_type = task_config_data.get("plugin_type", "ctrip_task")

                # 执行任务
                result = await self._run_task_plugin(plugin_type, task_config, ctx, options)

                if result.success:
                    return result

                if attempt < retry_count:
                    logger.warning(f"节点执行失败，重试 {attempt + 1}/{retry_count}")
                    await asyncio.sleep(2)
                else:
                    return result

            except asyncio.TimeoutError:
                last_error = TimeoutError(f"节点 {node.id} 超时")
                logger.warning(f"节点超时 (尝试 {attempt + 1}/{retry_count + 1})")
            except Exception as e:
                last_error = e
                logger.warning(f"节点异常 (尝试 {attempt + 1}/{retry_count + 1}): {e}")

            if attempt < retry_count:
                await asyncio.sleep(2)

        return TaskResult(
            success=False,
            message=str(last_error) if last_error else "未知错误",
        )

    async def _run_task_plugin(
        self,
        plugin_type: str,
        task_config: TaskConfig,
        ctx: TaskContext,
        options: ExecutionOptions,
    ) -> TaskResult:
        """运行任务插件
        
        当前实现：回退到现有的workflow执行器
        未来：通过插件注册表动态加载插件
        """
        # 合并配置
        merged_config = {**ctx.config, **task_config.config}
        ctx.config = merged_config

        if plugin_type == "ctrip_task":
            # 回退到现有携程工作流
            return await self._run_legacy_ctrip_workflow(ctx)
        else:
            logger.warning(f"未知的插件类型: {plugin_type}，使用默认携程工作流")
            return await self._run_legacy_ctrip_workflow(ctx)

    async def _run_legacy_ctrip_workflow(self, ctx: TaskContext) -> TaskResult:
        """运行现有携程工作流（兼容层）"""
        from src.automation.workflows.labor_workflow_runner import LaborWorkflowRunner


        try:
            # 获取必要的账号信息
            ctrip_account = ctx.config.get("ctrip_account")
            labor_account = ctx.config.get("labor_account")

            if not ctrip_account or not labor_account:
                return TaskResult(success=False, message="缺少账号配置")

            # 创建工作流运行器
            runner = LaborWorkflowRunner(ctx.page)
            
            # 执行任务
            await runner.run_auto_tasks(
                labor_account=labor_account,
                ctrip_account=ctrip_account,
                env_id=ctx.env_id,
            )

            completed = runner.stats.get("completed", 0)
            
            return TaskResult(
                success=completed > 0,
                tasks_completed=completed,
                message=f"完成 {completed} 个任务",
            )

        except Exception as e:
            logger.error(f"携程工作流执行失败: {e}")
            return TaskResult(success=False, message=str(e))

    def cancel(self) -> None:
        """取消当前执行"""
        self._cancelled = True
        logger.info("请求取消任务流执行")

    def get_flow_by_id(self, flow_id: int) -> TaskFlow | None:
        """根据ID获取任务流"""
        flow_data = self._task_flow_repo.get_by_id(flow_id)
        if flow_data:
            return TaskFlow.from_dict(flow_data)
        return None

    def get_flow_by_name(self, name: str) -> TaskFlow | None:
        """根据名称获取任务流"""
        flow_data = self._task_flow_repo.get_by_name(name)
        if flow_data:
            return TaskFlow.from_dict(flow_data)
        return None
