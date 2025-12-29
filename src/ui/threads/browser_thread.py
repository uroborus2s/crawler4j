"""浏览器启动线程模块。

负责手动启动环境时的浏览器打开和自动化执行。
使用统一工作流执行器，支持 input_callback 进行验证码等交互输入。
"""

import asyncio
import threading

from PyQt6.QtCore import QThread, pyqtSignal

from src.core.models.ctrip_account import CtripAccount
from src.core.models.environment import Environment
from src.core.models.labor_account import LaborAccount
from src.core.workflow_executor import (
    WorkflowResultType,
    execute_environment_workflow,
)
from src.utils.logger import logger
from src.utils.storage import (
    CtripAccountRepository,
    EnvironmentRepository,
    LaborAccountRepository,
)


class BrowserLauncherThread(QThread):
    """手动启动环境的线程。
    
    职责:
    1. 加载环境和账号数据
    2. 智能绑定劳保账号（如未绑定）
    3. 调用统一工作函数（支持 input_callback）
    4. 发射完成信号
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
        
        self.ctrip_repo = CtripAccountRepository()
        self.labor_repo = LaborAccountRepository()
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
            # 1. 加载环境和账号数据
            env, ctrip_account, labor_account = self._load_data()
            
            if not env:
                self.finished_signal.emit(False, "无法加载环境数据")
                return
            
            if not ctrip_account:
                logger.warning("携程账号不存在，将尝试手动输入模式")
                # 创建空账号对象用于手动输入
                ctrip_account = CtripAccount(
                    id=None,
                    country_code="+86",
                    phone_number="",
                )
            
            if not labor_account:
                self.finished_signal.emit(False, "无可用的劳保账号")
                return
            
            logger.info(f"准备执行自动化: 携程={ctrip_account.phone_number}, 劳保={labor_account.phone}")
            
            # 2. 调用统一工作函数
            result = asyncio.run(
                execute_environment_workflow(
                    environment=env,
                    ctrip_account=ctrip_account,
                    labor_account=labor_account,
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
    
    def _load_data(self) -> tuple[Environment | None, CtripAccount | None, LaborAccount | None]:
        """加载环境和账号数据。"""
        env = None
        ctrip_account = None
        labor_account = None
        
        # 加载环境
        if self.env_id:
            env_data = self.env_repo.get_by_id(self.env_id)
            if env_data:
                env = Environment.from_dict(env_data)
                # 使用环境关联的账号 ID
                if not self.ctrip_account_id:
                    self.ctrip_account_id = env_data.get("ctrip_account_id")
                if not self.labor_account_id:
                    self.labor_account_id = env_data.get("labor_account_id")
        else:
            # 无环境 ID，创建临时环境对象
            env = Environment(
                id=None,
                ctrip_account_id=self.ctrip_account_id,
                labor_account_id=self.labor_account_id,
                browser_profile_id=self.profile_id,
            )
        
        # 加载携程账号
        if self.ctrip_account_id:
            acc_data = self.ctrip_repo.get_by_id(self.ctrip_account_id)
            if acc_data:
                ctrip_account = CtripAccount(**acc_data)
        
        # 加载劳保账号
        if self.labor_account_id:
            labor_data = self.labor_repo.get_by_id(self.labor_account_id)
            if labor_data:
                labor_account = LaborAccount.from_dict(labor_data)
        
        # 智能绑定：如果未绑定劳保账号，自动选择绑定次数最少的账号
        if not labor_account and self.env_id:
            least_bound = self.labor_repo.get_least_bound()
            if least_bound:
                # 绑定到环境并增加计数
                self.env_repo.update(self.env_id, {"labor_account_id": least_bound["id"]})
                self.labor_repo.increment_bind_count(least_bound["id"])
                labor_account = LaborAccount.from_dict(least_bound)
                logger.info(f"✅ 自动绑定劳保账号: {labor_account.phone}")
            else:
                logger.warning("没有可用的劳保账号进行自动绑定")
        
        return env, ctrip_account, labor_account
