"""网络工具 (HTTP/Network Utils)。

基础 HTTP 客户端封装，提供共享的 aiohttp ClientSession。
"""

import asyncio
from typing import Any, Optional

import aiohttp

# 使用 Foundation 内部的 logger
from src.core.foundation.logging import logger


class AsyncHttpClient:
    """异步 HTTP 客户端。"""
    
    _session: Optional[aiohttp.ClientSession] = None
    
    @classmethod
    async def get_session(cls) -> aiohttp.ClientSession:
        """获取或创建共享的 ClientSession。"""
        current_loop = asyncio.get_running_loop()
        
        # 获取代理配置
        from src.core.system.config_center import get_config_center

        config = get_config_center()
        proxy_mode = config.get("network.proxy_mode")
        trust_env = (proxy_mode == "system")
        
        # 检查是否需要重建会话 (Loop mismatch 或 trust_env 变更)
        should_close = False
        if cls._session is not None:
             session_loop = getattr(cls._session, "_loop", None)
             current_trust_env = getattr(cls._session, "_trust_env", False)
             
             if session_loop != current_loop:
                 logger.debug("AsyncHttpClient: Loop mismatch detected")
                 should_close = True
             elif current_trust_env != trust_env:
                 logger.debug(f"AsyncHttpClient: Proxy mode changed ({current_trust_env} -> {trust_env})")
                 should_close = True
        
        if should_close and cls._session and not cls._session.closed:
             await cls._session.close()
             cls._session = None

        if cls._session is None or cls._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            connector = aiohttp.TCPConnector(limit=100, ttl_dns_cache=300)
            cls._session = aiohttp.ClientSession(
                timeout=timeout, 
                connector=connector,
                trust_env=trust_env 
            )
        return cls._session

    @classmethod
    def _get_proxy(cls) -> str | None:
        """获取手动代理设置。"""
        from src.core.system.config_center import get_config_center

        config = get_config_center()
        mode = config.get("network.proxy_mode")
        
        if mode == "manual":
            return config.get("network.http_proxy")
        return None

    @classmethod
    async def close(cls):
        """关闭共享会话。"""
        if cls._session and not cls._session.closed:
            await cls._session.close()
            cls._session = None
            logger.info("AsyncHttpClient session closed")

    @classmethod
    async def get(cls, url: str, **kwargs) -> Any:
        """GET 请求。"""
        session = await cls.get_session()
        
        # 注入代理
        proxy = cls._get_proxy()
        if proxy and "proxy" not in kwargs:
            kwargs["proxy"] = proxy
            
        async with session.get(url, **kwargs) as response:
            return await cls._handle_response(response)

    @classmethod
    async def post(cls, url: str, json: dict | None = None, **kwargs) -> Any:
        """POST 请求。"""
        session = await cls.get_session()
        
        # 注入代理
        proxy = cls._get_proxy()
        if proxy and "proxy" not in kwargs:
            kwargs["proxy"] = proxy
            
        async with session.post(url, json=json, **kwargs) as response:
            return await cls._handle_response(response)

    @staticmethod
    async def _handle_response(response: aiohttp.ClientResponse) -> Any:
        """处理响应并解析 JSON。"""
        try:
            if response.content_type == 'application/json':
                return await response.json()
            return await response.text()
        except Exception as e:
            logger.error(f"Failed to parse response from {response.url}: {e}")
            raise
