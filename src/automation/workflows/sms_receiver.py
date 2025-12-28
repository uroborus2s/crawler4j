"""SMS receiver module.

Handles fetching verification codes from SMS platforms.
"""

import asyncio
import re
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

    async def get_code(self, timeout: int = 120, interval: int = 5) -> Optional[str]:
        """Poll the SMS platform for a verification code.
        
        Args:
            timeout: Maximum wait time in seconds.
            interval: Polling interval in seconds.
            
        Returns:
            Verification code if found, None otherwise.
        """
        logger.info(f"开始获取验证码: {self.phone} (平台: {self.platform_type}, 超时: {timeout}s)")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                if self.platform_type == "haoma":
                    # HaoMa platform implementation
                    # Usually: GET /api/handler?action=getSms&token=TOKEN&item_id=ITEM_ID&mobile=PHONE
                    # Note: This is a heuristic implementation based on common patterns.
                    # Ideally we need the 'item_id' (project ID) as well, but here we assume it's pre-configured or part of the config.
                    # For now, we assume the base_url includes the endpoint path.
                    
                    # Example HaoMa API structure:
                    # http://api.haoma.com/sms/?token=KEY&sid=PROJECT_ID&phone=PHONE
                    
                    url = self.base_url
                    params = {
                        "token": self.api_key,
                        "phone": self.phone,
                        # "sid": "PROJECT_ID" # TODO: Pass project/item ID if needed
                    }
                    
                    # If the user put the full request URL in sms_platform_url, we just use it.
                    # Otherwise we might need to append logic.
                    
                else:
                    # Generic pattern for other SMS platforms
                    url = self.base_url
                    params = {
                        "token": self.api_key,
                        "phone": self.phone,
                        "action": "getMessage" 
                    }
                
                response = await asyncio.to_thread(
                    requests.get, url, params=params, timeout=10
                )
                
                if response.status_code == 200:
                    text = response.text
                    # logger.debug(f"短信平台响应: {text}")
                    
                    # HaoMa success usually starts with "success|" or similar, or just the message
                    # But often it returns "Message|Content"
                    
                    if "未获取" in text or "等待" in text or "0" == text:
                        pass # Continue waiting
                    else:
                        # Attempt to find 4-6 digit code
                        # Handle HaoMa specific "1|message" format if exists
                        content = text
                        if "|" in text:
                            parts = text.split("|")
                            if len(parts) > 1 and len(parts[0]) < 5: # likely status code
                                content = parts[1]
                                
                        match = re.search(r"(\d{4,6})", content)
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
