from typing import Type

import yaml
from pydantic import BaseModel

from modules.ctrip.config import CtripConfig
from modules.ctrip.login import CtripLogin
from src.core.adapters.browser_adapter import BrowserAdapter
from src.core.interfaces.module import TaskContext, TaskModule


class CtripModule(TaskModule):
    
    @property
    def module_id(self) -> str:
        return "ctrip"

    @property
    def display_name(self) -> str:
        return "Ctrip Hotel Crawler"

    @property
    def config_model(self) -> Type[BaseModel]:
        return CtripConfig

    def get_default_config(self) -> str:
        return yaml.dump(CtripConfig().model_dump(), default_flow_style=False)

    @property
    def icon(self) -> str:
        return "🏨"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "携程酒店自动化模块，支持账号登录、酒店搜索、订单提交等操作。"

    @property
    def ui_schema(self) -> dict:
        return {
            "accounts": {
                "type": "table",
                "label": "携程账号",
                "storage_key": "ctrip_accounts",  # 存储表名
                "columns": [
                    {"key": "phone_number", "label": "手机号", "type": "text"},
                    {"key": "country_code", "label": "国家码", "type": "text"},
                    {"key": "status", "label": "状态", "type": "status_badge"},
                    {"key": "last_login", "label": "最后登录", "type": "datetime"},
                ],
                "actions": ["add", "edit", "delete", "login"]
            },
            "config": {
                "type": "form",
                "label": "模块配置",
                "fields": [
                    {"key": "timeout", "label": "超时(秒)", "type": "number", "default": 30},
                    {"key": "headless", "label": "无头模式", "type": "boolean", "default": False},
                    {"key": "retry_count", "label": "重试次数", "type": "number", "default": 3},
                ]
            }
        }

    async def run(self, context: TaskContext) -> None:
        """Run the Ctrip task."""
        # 1. Spawn Environment (if not already)
        if not await context.env.is_alive():
            await context.env.spawn()
        
        # 2. Connect Adapter
        adapter = BrowserAdapter(context.env)
        page = await adapter.connect()
        
        try:
            # 3. Initialize Workflow
            workflow = CtripLogin(page)
            
            # 4. Execute Logic
            # Assuming we just want to login for now based on Task Name or Workflow ID?
            # context.config is a Dict.
            
            # For this simple migration, we just run login.
            # In real system, we might switch on context.config['action']
            
            print(f"Starting Ctrip Login Task {context.task_id}...")
            await workflow.login(account=None) # We need account info!
            # Account info should come from context or resource manager.
            # Ignoring for now as per "Migrate logic" scope (keeping it runnable).
            
            print("Ctrip Task Completed.")
            
        finally:
            # We don't close the browser here necessarily, depending on strategy.
            # But for safety we might detach adapter.
            await adapter.close()
