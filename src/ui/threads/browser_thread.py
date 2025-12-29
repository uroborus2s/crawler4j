"""浏览器启动线程模块。

负责手动启动环境时的浏览器打开和自动化执行。
使用统一工作流执行器，支持 input_callback 进行验证码等交互输入。
"""

import asyncio
import threading

from PyQt6.QtCore import QThread, pyqtSignal

from src.core.models.environment import Environment
from src.core.workflow_executor import (
    WorkflowResultType,
    execute_environment_workflow,
)
from src.utils.logger import logger
from src.utils.storage import EnvironmentRepository


class BrowserLauncherThread(QThread):
    """手动启动环境的线程。
    
    职责:
    1. 加载环境数据
    2. 调用统一工作函数（支持 input_callback）
    3. 发射完成信号
    """
    
    finished_signal = pyqtSignal(bool, str)  # success, message
    input_signal = pyqtSignal(dict, object)  # container, event
    
    def __init__(
        self,
        profile_id: str,
        ctrip_account_id: int | None = None,
        labor_account_id: int | None = None,
        env_id: int | None = None,
    ):
        super().__init__()
        self.profile_id = profile_id
        self.ctrip_account_id = ctrip_account_id
        self.labor_account_id = labor_account_id
        self.env_id = env_id
        
        self.env_repo = EnvironmentRepository()
    
    def get_user_input(self, title: str, label: str, default: str = "", text: str = "") -> str | None:
        """请求 UI 线程安全的用户输入。"""
        event = threading.Event()
        
        display_text = text if text else default
        container = {"title": title, "label": label, "text": display_text, "value": None}
        
        self.input_signal.emit(container, event)
        event.wait()  # 阻塞直到 UI 响应
        
        return container.get("value")
    
    def run(self):
        """执行线程主逻辑。"""
        try:
            # 1. 加载/构建环境对象
            env = self._load_environment()
            
            if not env:
                self.finished_signal.emit(False, "无法加载环境数据")
                return
            
            logger.info(f"准备执行自动化: ENV-{env.id or 'temp'}")
            
            # 2. 调用统一工作函数（手动模式带 input_callback）
            result = asyncio.run(
                execute_environment_workflow(
                    environment=env,
                    input_callback=self.get_user_input,  # 支持手动输入
                )
            )
            
            # 3. 处理结果
            success = result.result_type in (
                WorkflowResultType.SUCCESS,
                WorkflowResultType.NO_TASK,
            )
            
            # 4. 更新环境状态
            if self.env_id:
                self.env_repo.update_status(self.env_id, "idle")
            
            self.finished_signal.emit(success, result.message)
            
        except Exception as e:
            logger.error(f"浏览器启动或自动化失败: {e}")
            if self.env_id:
                self.env_repo.update_status(self.env_id, "error")
            self.finished_signal.emit(False, str(e))
    
    def _load_environment(self) -> Environment | None:
        """加载或构建环境对象。"""
        # 有 env_id：从数据库加载
        if self.env_id:
            env_data = self.env_repo.get_by_id(self.env_id)
            if env_data:
                return Environment.from_dict(env_data)
            return None
        
        # 无 env_id：创建临时环境对象
        return Environment(
            id=None,
            ctrip_account_id=self.ctrip_account_id,
            labor_account_id=self.labor_account_id,
            browser_profile_id=self.profile_id,
        )
