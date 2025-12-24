"""SMS receiver module.

Handles fetching verification codes from SMS platforms.
"""

import re
import asyncio
import time
from typing import Optional

import requests

from src.utils.logger import logger


class SMSReceiver:
    """Utility for fetching SMS verification codes.
    
    Supports various platforms via generic API structure.
    """
    
    def __init__(
        self, 
        base_url: str, 
        api_key: str, 
        platform_type: str = "",
        phone: str = ""
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.platform_type = platform_type
        self.phone = phone

    async def get_code(self, timeout: int = 60, interval: int = 5) -> Optional[str]:
        """Poll the SMS platform for a verification code.
        
        Args:
            timeout: Maximum wait time in seconds.
            interval: Polling interval in seconds.
            
        Returns:
            Verification code if found, None otherwise.
        """
        logger.info(f"开始获取验证码: {self.phone} (超时: {timeout}s)")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Generic pattern for SMS platforms
                # Usually: GET /api?token=LINK&phone=PHONE&action=getCode
                url = self.base_url
                params = {
                    "token": self.api_key,
                    "phone": self.phone,
                    "action": "getMessage" # Placeholder action
                }
                
                # Note: Real implementation would switch based on platform_type
                response = await asyncio.to_thread(
                    requests.get, url, params=params, timeout=10
                )
                
                if response.status_code == 200:
                    text = response.text
                    logger.debug(f"短信平台响应: {text}")
                    
                    # Extract 4-6 digit code
                    match = re.search(r"(\d{4,6})", text)
                    if match:
                        code = match.group(1)
                        logger.info(f"成功获取验证码: {code}")
                        return code
                
            except Exception as e:
                logger.warning(f"获取验证码请求失败: {e}")
                
            await asyncio.sleep(interval)
            
        logger.error(f"获取验证码超时: {self.phone}")
        return None

    @classmethod
    async def fetch(
        cls, 
        phone: str, 
        url: str, 
        key: str, 
        p_type: str = "", 
        timeout: int = 60
    ) -> Optional[str]:
        """Convenience method for fetching code."""
        receiver = cls(url, key, p_type, phone)
        return await receiver.get_code(timeout)
