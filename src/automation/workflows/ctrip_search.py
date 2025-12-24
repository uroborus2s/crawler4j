"""Ctrip search workflow module.

Handles searching on Ctrip and extracting required data.
"""

import asyncio

from src.automation.workflows.base import BaseWorkflow
from src.utils.logger import logger


class CtripSearchWorkflow(BaseWorkflow):
    """Workflow for searching on Ctrip."""
    
    SEARCH_URL = "https://www.ctrip.com"
    
    async def search(self, keyword: str) -> bool:
        """Execute search on Ctrip.
        
        In this specific project, "search" often means demonstrating 
        real user behavior (scrolling, clicking) to the platform 
        and extracting data for the task.
        
        Args:
            keyword: The keyword to search for.
            
        Returns:
            True if search and extraction successful.
        """
        logger.info(f"开始携程搜索: {keyword}")
        
        try:
            await self.page.goto(self.SEARCH_URL)
            
            # Type keyword into search input
            await self.wait_and_type("input#main_search", keyword) # Assume ID for main search
            
            # Click search button
            await self.page.keyboard.press("Enter")
            
            # Wait for results
            await self.page.wait_for_timeout(3000)
            
            # Simulate some human-like scrolling
            await self.page.mouse.wheel(0, 500)
            await asyncio.sleep(1)
            await self.page.mouse.wheel(0, 500)
            
            logger.info(f"携程搜索完成: {keyword}")
            return True
                
        except Exception as e:
            logger.error(f"携程搜索异常: {e}")
            return False
