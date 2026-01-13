"""接码平台客户端模块。

封装接码平台API调用：登录、取号、取码。
"""

import asyncio
from dataclasses import dataclass

import httpx

from src.core.foundation.logging import logger


@dataclass
class SMSPlatformConfig:
    """接码平台配置。"""

    host: str  # 域名，格式如 "3.112.30.233:8000"
    username: str
    password: str
    product_id: str


class SMSPlatformClient:
    """接码平台客户端。

    API规范：
    - 登录: /api/user/apiLogin
    - 取号: /api/phone/getPhone
    - 取码: /api/phone/getCode
    """

    def __init__(self, config: SMSPlatformConfig):
        self.config = config
        self._token: str | None = None
        self._base_url = f"http://{config.host}"

    async def login(self) -> str | None:
        """登录获取 token。

        Returns:
            成功返回 token，失败返回 None
        """
        url = f"{self._base_url}/api/user/apiLogin"
        params = {
            "username": self.config.username,
            "password": self.config.password,
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url, params=params)
                data = resp.json()

                if data.get("code") == 200:
                    self._token = data["result"]["token"]
                    logger.info("✅ 接码平台登录成功")
                    return self._token
                else:
                    logger.error(f"接码平台登录失败: {data.get('msg')}")
                    return None
        except Exception as e:
            logger.error(f"接码平台登录异常: {e}")
            return None

    async def get_phone(self, max_retries: int = 100) -> str | None:
        """取号：循环重试直到成功。

        Args:
            max_retries: 最大重试次数

        Returns:
            成功返回手机号，失败返回 None
        """
        if not self._token:
            if not await self.login():
                return None

        url = f"{self._base_url}/api/phone/getPhone"
        params = {
            "productId": self.config.product_id,
            "username": self.config.username,
            "token": self._token,
        }

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.get(url, params=params)
                    data = resp.json()

                    if data.get("code") == 200:
                        phone = data["result"]["phones"]
                        logger.info(f"✅ 取号成功: {phone}")
                        return phone
                    elif data.get("code") == 500 and "卡余量不足" in data.get(
                        "msg", ""
                    ):
                        # 循环重试
                        if attempt % 10 == 0:
                            logger.debug(f"取号重试中 ({attempt}/{max_retries})...")
                        await asyncio.sleep(0.1)
                    else:
                        logger.error(f"取号失败: {data.get('msg')}")
                        return None
            except Exception as e:
                logger.error(f"取号异常: {e}")
                await asyncio.sleep(0.1)

        logger.error(f"取号超过最大重试次数 ({max_retries})")
        return None

    async def get_code(self, phone: str, timeout: int = 180) -> str | None:
        """取码：3分钟超时轮询。

        Args:
            phone: 手机号
            timeout: 超时时间（秒），默认3分钟

        Returns:
            成功返回验证码，超时返回 None
        """
        if not self._token:
            if not await self.login():
                return None

        url = f"{self._base_url}/api/phone/getCode"
        params = {
            "productId": self.config.product_id,
            "username": self.config.username,
            "token": self._token,
            "phone": phone,
        }

        start_time = asyncio.get_event_loop().time()
        poll_count = 0

        while asyncio.get_event_loop().time() - start_time < timeout:
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.get(url, params=params)
                    data = resp.json()

                    if data.get("code") == 200:
                        result = data.get("result", {})
                        code = result.get("code")
                        status = result.get("status")

                        if code and status == 1:
                            logger.info(f"✅ 取码成功: {code}")
                            return code

                    # 未获取到，继续轮询
                    poll_count += 1
                    if poll_count % 10 == 0:
                        elapsed = int(asyncio.get_event_loop().time() - start_time)
                        logger.debug(f"等待验证码中... ({elapsed}s/{timeout}s)")

                    await asyncio.sleep(0.1)

            except Exception as e:
                logger.warning(f"取码请求异常: {e}")
                await asyncio.sleep(0.1)

        logger.error(f"取码超时 ({timeout}s)")
        return None


def create_sms_client_from_config() -> SMSPlatformClient | None:
    """从全局配置创建接码平台客户端。

    Returns:
        配置完整时返回客户端，否则返回 None
    """
    from src.config import config

    host = config.sms_platform_host
    username = config.sms_platform_username
    password = config.sms_platform_password
    product_id = config.sms_platform_product_id

    if not all([host, username, password, product_id]):
        return None

    return SMSPlatformClient(
        SMSPlatformConfig(
            host=host,
            username=username,
            password=password,
            product_id=product_id,
        )
    )
