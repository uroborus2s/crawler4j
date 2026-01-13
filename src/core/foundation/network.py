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
        
        if cls._session is not None:
            session_loop = getattr(cls._session, "_loop", None)
            if session_loop != current_loop:
                logger.debug("AsyncHttpClient: Loop mismatch detected, recreating session")
                if not cls._session.closed:
                    await cls._session.close()
                cls._session = None

        if cls._session is None or cls._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            connector = aiohttp.TCPConnector(limit=100, ttl_dns_cache=300)
            cls._session = aiohttp.ClientSession(
                timeout=timeout, 
                connector=connector,
                trust_env=False 
            )
        return cls._session

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
        async with session.get(url, **kwargs) as response:
            return await cls._handle_response(response)

    @classmethod
    async def post(cls, url: str, json: dict | None = None, **kwargs) -> Any:
        """POST 请求。"""
        session = await cls.get_session()
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
